Prometheus server configuration example
=======================================

In this section an example of configuration of Prometheus with Service discovery file is shown (sd_file).
You can prepare 2 configuration files for prometheus:

* The configuration file -> **/home/ubuntu/config.yaml**
* The sd_file -> **/home/ubuntu/sd_file.yaml**

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

Then you can set an empty array as content for the sd_file.yaml:

.. code-block:: yaml

    []

Now you can run prometheus inside a docker container with the following bash command:

.. warning::
    Use the correct location of your **prometheus.yml** and **sd_file.yaml**.

.. code-block:: bash

    sudo docker run -p 9090:9090 -v /home/ubuntu/config.yaml:/etc/prometheus/prometheus.yml -v /home/ubuntu/sd_file.yaml:/etc/prometheus/sd_file.yaml prom/prometheus

.. important::
    You can now add your Prometheus server to the topology (see :doc:`prometheus_top_add`). The server sd_file, in this case, will be **/home/ubuntu/sd_file.yaml**.
