import logging
import typing
from typing import Any, Dict, List, Optional, Text, Tuple

from rasa.nlu.components import Component
from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.nlu.config import RasaNLUModelConfig
import rasa.utils.train_utils
from rasa.shared.nlu.training_data.message import Message
from rasa.nlu.constants import SPACY_DOCS, DENSE_FEATURIZABLE_ATTRIBUTES
from rasa.shared.core.domain import Domain

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens.doc import Doc
    from rasa.nlu.model import Metadata, InvalidModelError


class SpacyNLP(Component):
    """Component that loads the SpaCy language model."""

    defaults = {
        # name of the language model to load - if it is not set
        # we will be looking for a language model that is named
        # after the language of the model, e.g. `en`
        "model": None,
        # when retrieving word vectors, this will decide if the casing
        # of the word is relevant. E.g. `hello` and `Hello` will
        # retrieve the same vector, if set to `False`. For some
        # applications and models it makes sense to differentiate
        # between these two words, therefore setting this to `True`.
        "case_sensitive": False,
    }

    def __init__(
        self, component_config: Dict[Text, Any] = None, nlp: "Language" = None
    ) -> None:
        """Initialize the component. See parent class for more information."""
        self.nlp = nlp
        super().__init__(component_config)

    @staticmethod
    def _load_model(spacy_model_name: Text) -> "Language":
        """Try loading the model, catching the OSError if missing."""
        import spacy

        try:
            return spacy.load(spacy_model_name, disable=["parser"])
        except OSError:
            raise InvalidModelError(
                "Model '{}' is not a linked spaCy model.  "
                "Please download and/or link a spaCy model, "
                "e.g. by running:\npython -m spacy download "
                "en_core_web_md\npython -m spacy link "
                "en_core_web_md en".format(spacy_model_name)
            )

    @classmethod
    def required_packages(cls) -> List[Text]:
        """Specify which python packages need to be installed.

        See parent class for more information.
        """
        return ["spacy"]

    @classmethod
    def create(
        cls,
        component_config: Dict[Text, Any],
        model_config: RasaNLUModelConfig,
        domain: Optional[Domain] = None,
    ) -> "SpacyNLP":
        """Creates this component (e.g. before a training is started).

        See parent class for more information.
        """
        component_config = rasa.utils.train_utils.override_defaults(
            cls.defaults, component_config
        )

        spacy_model_name = component_config.get("model")

        # if no model is specified, we fall back to the language string
        if not spacy_model_name:
            spacy_model_name = model_config.language
            component_config["model"] = model_config.language

        logger.info(f"Trying to load spacy model with name '{spacy_model_name}'")

        nlp = cls._load_model(spacy_model_name)

        cls._ensure_proper_language_model(nlp)
        return cls(component_config, nlp)

    @classmethod
    def cache_key(
        cls, component_meta: Dict[Text, Any], model_metadata: "Metadata"
    ) -> Optional[Text]:
        """This key is used to cache components."""
        # Fallback, use the language name, e.g. "en",
        # as the model name if no explicit name is defined
        spacy_model_name = component_meta.get("model", model_metadata.language)

        return cls.name + "-" + spacy_model_name

    def provide_context(self) -> Dict[Text, Any]:
        """Initialize this component for a new pipeline.

        See parent class for more information.
        """
        return {"spacy_nlp": self.nlp}

    def _doc_for_text(self, text: Text) -> "Doc":
        return self.nlp(self._preprocess_text(text))

    def _preprocess_text(self, text: Optional[Text]) -> Text:
        if text is None:
            # converted to empty string so that it can still be passed to spacy.
            # Another option could be to neglect tokenization of the attribute of
            # this example, but since we are processing in batch mode, it would
            # get complex to collect all processed and neglected examples.
            text = ""
        if self.component_config.get("case_sensitive"):
            return text
        else:
            return text.lower()

    def _get_text(self, example: Message, attribute: Text) -> Text:
        return self._preprocess_text(example.get(attribute))

    @staticmethod
    def _merge_content_lists(
        indexed_training_samples: List[Tuple[int, Text]],
        doc_lists: List[Tuple[int, "Doc"]],
    ) -> List[Tuple[int, "Doc"]]:
        """Merge lists with processed Docs back into their original order."""
        dct = dict(indexed_training_samples)
        dct.update(dict(doc_lists))
        return sorted(dct.items())

    @staticmethod
    def _filter_training_samples_by_content(
        indexed_training_samples: List[Tuple[int, Text]]
    ) -> Tuple[List[Tuple[int, Text]], List[Tuple[int, Text]]]:
        """Separates empty training samples from content bearing ones."""
        docs_to_pipe = list(
            filter(
                lambda training_sample: training_sample[1] != "",
                indexed_training_samples,
            )
        )
        empty_docs = list(
            filter(
                lambda training_sample: training_sample[1] == "",
                indexed_training_samples,
            )
        )
        return docs_to_pipe, empty_docs

    def _process_content_bearing_samples(
        self, samples_to_pipe: List[Tuple[int, Text]]
    ) -> List[Tuple[int, "Doc"]]:
        """Sends content bearing training samples to spaCy's pipe."""
        docs = [
            (to_pipe_sample[0], doc)
            for to_pipe_sample, doc in zip(
                samples_to_pipe,
                [
                    doc
                    for doc in self.nlp.pipe(
                        [txt for _, txt in samples_to_pipe], batch_size=50
                    )
                ],
            )
        ]
        return docs

    def _process_non_content_bearing_samples(
        self, empty_samples: List[Tuple[int, Text]]
    ) -> List[Tuple[int, "Doc"]]:
        """Creates empty Doc-objects from zero-lengthed training samples strings."""
        from spacy.tokens import Doc

        n_docs = [
            (empty_sample[0], doc)
            for empty_sample, doc in zip(
                empty_samples, [Doc(self.nlp.vocab) for doc in empty_samples]
            )
        ]
        return n_docs

    def _docs_for_training_examples(
        self, training_examples: List[Message]
    ) -> Dict[Text, List[Any]]:
        attribute_docs = {}
        for attribute in DENSE_FEATURIZABLE_ATTRIBUTES:
            texts = [self._get_text(e, attribute) for e in training_examples]
            # Index and freeze indices of the training samples for preserving the order
            # after processing the data.
            indexed_training_samples = [(idx, text) for idx, text in enumerate(texts)]

            samples_to_pipe, empty_samples = self._filter_training_samples_by_content(
                indexed_training_samples
            )

            content_bearing_docs = self._process_content_bearing_samples(
                samples_to_pipe
            )

            non_content_bearing_docs = self._process_non_content_bearing_samples(
                empty_samples
            )

            attribute_document_list = self._merge_content_lists(
                indexed_training_samples,
                content_bearing_docs + non_content_bearing_docs,
            )

            # Since we only need the training samples strings,
            # we create a list to get them out of the tuple.
            attribute_docs[attribute] = [doc for _, doc in attribute_document_list]
        return attribute_docs

    def train(
        self,
        training_data: TrainingData,
        config: Optional[RasaNLUModelConfig] = None,
        **kwargs: Any,
    ) -> None:
        """Train this component on the given chunk.

        See parent class for more information.
        """
        attribute_docs = self._docs_for_training_examples(
            training_data.training_examples
        )
        for attribute in DENSE_FEATURIZABLE_ATTRIBUTES:
            for idx, example in enumerate(training_data.training_examples):
                example_attribute_doc = attribute_docs[attribute][idx]
                if len(example_attribute_doc):
                    # If length is 0, that means the initial text feature
                    # was None and was replaced by ''
                    # in preprocess method
                    example.set(SPACY_DOCS[attribute], example_attribute_doc)

    def process(self, message: Message, **kwargs: Any) -> None:
        """Process an incoming message. See parent class for more information."""
        for attribute in DENSE_FEATURIZABLE_ATTRIBUTES:
            if message.get(attribute):
                message.set(
                    SPACY_DOCS[attribute], self._doc_for_text(message.get(attribute))
                )

    @classmethod
    def load(
        cls,
        meta: Dict[Text, Any],
        model_dir: Text = None,
        model_metadata: "Metadata" = None,
        cached_component: Optional["SpacyNLP"] = None,
        **kwargs: Any,
    ) -> "SpacyNLP":

        if cached_component:
            return cached_component

        model_name = meta.get("model")

        nlp = cls._load_model(model_name)
        cls._ensure_proper_language_model(nlp)
        return cls(meta, nlp)

    @staticmethod
    def _ensure_proper_language_model(nlp: Optional["Language"]) -> None:
        """Checks if the spacy language model is properly loaded.

        Raises an exception if the model is invalid.
        """
        if nlp is None:
            raise Exception(
                "Failed to load spacy language model. "
                "Loading the model returned 'None'."
            )
        if nlp.path is None:
            # Spacy sets the path to `None` if
            # it did not load the model from disk.
            # In this case `nlp` is an unusable stub.
            raise Exception(
                "Failed to load spacy language model for "
                "lang '{}'. Make sure you have downloaded the "
                "correct model (https://spacy.io/docs/usage/)."
                "".format(nlp.lang)
            )
