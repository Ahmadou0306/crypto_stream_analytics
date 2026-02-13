import setuptools

setuptools.setup(
    name='crypto-stream-dataflow',
    version='1.0.0',
    description='Pipeline Dataflow pour crypto analytics',
    author='Ahmadou Ndiaye',
    py_modules=[  # ← Changement ici
        'CalculateIndicators',
        'CleanData',
        'ParsePubSubMessage'
    ],
    install_requires=[
        'apache-beam[gcp]==2.53.0',
        'google-cloud-bigquery==3.14.1',
        'google-cloud-pubsub==2.19.0',
        'google-cloud-storage==2.14.0',
    ],
)