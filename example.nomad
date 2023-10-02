variable "vcenters" {
  default = [
    "<VCENTER1 FQDN>",
    "<VCENTER2 FQDN>"
  ]
}
job "gather_vmproperties" {
  datacenters = ["<DC>"]
  type = "batch"
  
  periodic {
  	cron       = "30 5 * * *"       # Schedule to run daily at 1:30 am eastern
  	prohibit_overlap = true         # Prevent concurrent runs
  	time_zone   = "UTC"             # Set the timezone if required
	}	
  # Dynamically create a task group for each vCenter
  dynamic "group" {
    for_each = var.vcenters
    labels   = [group.value]
    content {
      # This is only included so we can pass the NOMAD_IP variable.  Seems stupid?
      network {
        port "logging" {}
      }
      task "vmproperties" {
        driver = "docker"

        config {
          # This is specific to my use case, I have fluentd logging on each nomad host
          logging {
            type = "fluentd"
            config {
              fluentd-address = "${NOMAD_IP_logging}:24224"
              tag             = "python.vmproperties"
              env-regex       = "^NOMAD"
              fluentd-async   = true
            }
          }
          image = "<DOCKER IMAGE HERE>"
        }
        vault {
          policies = ["<VAULT POLICY>"]
        }
        template {
          data        = <<EOF
                    {{ with secret "<PATH TO SECRET>/vcenters" }}
                    VSPHERE_USER={{ .Data.vc_user }}
                    VSPHERE_PASSWORD={{ .Data.vc_password }}
                    {{ end }}
                    {{ with secret "<PATH TO SECRET>/database" }}
                    DB_HOST={{ .Data.db_host }}
                    DB_PORT={{ .Data.db_port }}
                    DB_USER={{ .Data.db_user }}
                    DB_PASSWORD={{ .Data.db_password }}
                    DB_NAME={{ .Data.db_name }}
                    {{ end }}
                    EOF
          destination = "secrets.env"
          env         = true
        }
        env {
            VCENTER = "${group.value}"
        }
        resources {
          cpu       = 100
          memory    = 600
        }
      }
    }
  }
}
