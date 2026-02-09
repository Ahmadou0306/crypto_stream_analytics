terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Pour stocker le state 
  # Créer manuellement le bucket avec gsutil mb -l europe-west1 gs://ton-project-terraform-state
  backend "gcs" {
    bucket      = "an-terraform-state-crypto_stream_analytics"
    prefix      = "terraform/state"
    credentials = "configs/credential.json"
  }
}

provider "google" {
  project     = var.project_id
  region      = var.region
  zone        = var.zone
  credentials = file(var.credentials_file)
}