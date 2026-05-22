"""Coach v1: event-driven spending-coach agent.

The Coach reacts to streaming spending signals produced by the sibling
`cockroachdb-watsonx-data-pipeline` repo. Two transport paths feed the same
in-process `SignalHandler`: the CRDB changefeed webhook (demo path) and
the Debezium Kafka topic (prod path).
"""
