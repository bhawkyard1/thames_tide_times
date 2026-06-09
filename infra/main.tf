terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Service account for the VM
resource "google_service_account" "app_sa" {
  account_id   = "thames-tide-app"
  display_name = "Thames Tide App VM"
}

# Grant it access to read secrets
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_compute_instance" "app_vm" {
  name         = "thames-tide-vm"
  machine_type = "e2-micro"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20 # GB
    }
  }

  network_interface {
    network = "default"
    access_config {} # gives it a public IP
  }

  service_account {
    email  = google_service_account.app_sa.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    startup-script = file("${path.module}/startup.sh")
  }

  tags = ["http-server", "https-server"]
}

# Firewall rules
resource "google_compute_firewall" "allow_web" {
  name    = "allow-web"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["http-server", "https-server"]
}

output "vm_ip" {
  value = google_compute_instance.app_vm.network_interface[0].access_config[0].nat_ip
}
