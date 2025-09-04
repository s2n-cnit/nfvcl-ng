Prometheus server configuration example
=======================================

In this section, there is an example of Prometheus configuration with Service Discovery (SD) enabled of files (sd_file).
You can prepare the main Prometheus configuration file at:

* **/home/ubuntu/prometheus.yaml**

In the configuration file (**prometheus.yml**) you have to setup the location of the sd_file

.. code-block:: yaml

    # my global config
    global:
      scrape_interval: 15s # Set the scrape interval to every 15 seconds. Default is every 1 minute.
      evaluation_interval: 15s # Evaluate rules every 15 seconds. The default is every 1 minute.
      # scrape_timeout is set to the global default (10s).

    # A scrape configuration containing exactly one endpoint to scrape:
    # Here it's Prometheus itself.
    scrape_configs:
      # The job name is added as a label `job=<job_name>` to any timeseries scraped from this config.
      - job_name: "prometheus"

        # metrics_path defaults to '/metrics'
        # scheme defaults to 'http'.

        static_configs:
          - targets: ["localhost:9090"]

      - job_name: "sd_file"
        file_sd_configs:
        - files:
          - "sd_file.yaml"
          refresh_interval: 1m

Then you can create the SD file **/home/ubuntu/sd_file.yaml** and set an empty array as content for the sd_file.yaml:

.. code-block:: yaml

    []

Now you can run prometheus inside a docker container with the following bash command:

.. warning::
    Use the correct location of your **prometheus.yml** and **sd_file.yaml**.

.. code-block:: bash

    sudo docker run -p 9090:9090 -v /home/ubuntu/config.yaml:/etc/prometheus/prometheus.yml -v /home/ubuntu/sd_file.yaml:/etc/prometheus/sd_file.yaml prom/prometheus

.. important::
    You can now add your Prometheus server to the topology (see :doc:`prometheus_top_add`). The server sd_file, in this case, will be **/home/ubuntu/sd_file.yaml**.
