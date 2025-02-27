variable "IMAGE_NAME" {
  default = "rasa/rasa"
}

variable "IMAGE_TAG" {
  default = "localdev"
}

variable "BASE_IMAGE_HASH" {
  default = "localdev"
}

variable "BASE_MITIE_IMAGE_HASH" {
  default = "localdev"
}

group "base-images" {
  targets = ["base", "base-mitie"]
}

target "base" {
  dockerfile = "docker/Dockerfile.base"
  tags       = ["${IMAGE_NAME}:base-${IMAGE_TAG}"]
  cache-to   = ["type=inline"]
}

target "base-mitie" {
  dockerfile = "docker/Dockerfile.base-mitie"
  tags       = ["${IMAGE_NAME}:base-mitie-${IMAGE_TAG}"]
  cache-to   = ["type=inline"]
}

target "default" {
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}"]

  args = {
    IMAGE_BASE_NAME = "${IMAGE_NAME}"
    BASE_IMAGE_HASH = "${BASE_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest",
  ]
}

target "full" {
  dockerfile = "docker/Dockerfile.full"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-full"]

  args = {
    IMAGE_BASE_NAME       = "${IMAGE_NAME}"
    BASE_IMAGE_HASH       = "${BASE_IMAGE_HASH}"
    BASE_MITIE_IMAGE_HASH = "${BASE_MITIE_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-full",
  ]
}

target "mitie-en" {
  dockerfile = "docker/Dockerfile.pretrained_embeddings_mitie_en"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-mitie-en"]

  args = {
    IMAGE_BASE_NAME       = "${IMAGE_NAME}"
    BASE_IMAGE_HASH       = "${BASE_IMAGE_HASH}"
    BASE_MITIE_IMAGE_HASH = "${BASE_MITIE_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-mitie-${BASE_MITIE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-mitie-en",
  ]
}

target "spacy-de" {
  dockerfile = "docker/Dockerfile.pretrained_embeddings_spacy_de"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-spacy-de"]

  args = {
    IMAGE_BASE_NAME = "${IMAGE_NAME}"
    BASE_IMAGE_HASH = "${BASE_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-spacy-de",
  ]
}

target "spacy-en" {
  dockerfile = "docker/Dockerfile.pretrained_embeddings_spacy_en"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-spacy-en"]

  args = {
    IMAGE_BASE_NAME = "${IMAGE_NAME}"
    BASE_IMAGE_HASH = "${BASE_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-spacy-en",
  ]
}
