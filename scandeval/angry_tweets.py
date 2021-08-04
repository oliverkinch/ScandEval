'''Sentiment evaluation of a language model on the AngryTweets dataset'''

from datasets import Dataset
import numpy as np
from typing import Tuple, Dict, List, Optional
import requests
import json
import logging

from .text_classification import TextClassificationBenchmark
from .utils import doc_inherit, InvalidBenchmark


logger = logging.getLogger(__name__)


class AngryTweetsBenchmark(TextClassificationBenchmark):
    '''Benchmark of language models on the AngryTweets dataset.

    Args:
        cache_dir (str, optional):
            Where the downloaded models will be stored. Defaults to
            '.benchmark_models'.
        learning_rate (float, optional):
            What learning rate to use when finetuning the models. Defaults to
            2e-5.
        warmup_steps (int, optional):
            The number of training steps in which the learning rate will be
            warmed up, meaning starting from nearly 0 and progressing up to
            `learning_rate` after `warmup_steps` many steps. Defaults to 50.
        batch_size (int, optional):
            The batch size used while finetuning. Defaults to 16.
        verbose (bool, optional):
            Whether to print additional output during evaluation. Defaults to
            False.

    Attributes:
        cache_dir (str): Directory where models are cached.
        learning_rate (float): Learning rate used while finetuning.
        warmup_steps (int): Number of steps used to warm up the learning rate.
        batch_size (int): The batch size used while finetuning.
        epochs (int): The number of epochs to finetune.
        num_labels (int): The number of NER labels in the dataset.
        label2id (dict): Conversion dict from NER labels to their indices.
        id2label (dict): Conversion dict from NER label indices to the labels.
    '''
    def __init__(self,
                 cache_dir: str = '.benchmark_models',
                 learning_rate: float = 2e-5,
                 warmup_steps: int = 50,
                 batch_size: int = 16,
                 verbose: bool = False):
        label2id = dict(neutral=0, positiv=1, negativ=2)
        super().__init__(num_labels=3,
                         epochs=5,
                         label2id=label2id,
                         cache_dir=cache_dir,
                         learning_rate=learning_rate,
                         warmup_steps=warmup_steps,
                         batch_size=batch_size,
                         verbose=verbose)

    @doc_inherit
    def _load_data(self) -> Tuple[Dataset, Dataset]:

        base_url= ('https://raw.githubusercontent.com/saattrupdan/ScandEval/'
                   'main/datasets/angry_tweets/')
        train_url = base_url + 'train.jsonl'
        test_url = base_url + 'test.jsonl'

        def get_dataset_from_url(url: str) -> Dataset:
            response = requests.get(url)
            records = response.text.split('\n')
            data = [json.loads(record) for record in records if record != '']
            docs = [data_dict['tweet'] for data_dict in data]
            labels = [data_dict['label'] for data_dict in data]
            dataset = Dataset.from_dict(dict(doc=docs, orig_label=labels))
            return dataset

        return get_dataset_from_url(train_url), get_dataset_from_url(test_url)

    @doc_inherit
    def _compute_metrics(self,
                         predictions_and_labels: tuple,
                         id2label: Optional[dict] = None) -> Dict[str, float]:
        predictions, labels = predictions_and_labels
        predictions = predictions.argmax(axis=-1)
        results = self._metric.compute(predictions=predictions,
                                       references=labels,
                                       average='macro')
        return dict(macro_f1=results['f1'])

    @doc_inherit
    def _log_metrics(self,
                     metrics: Dict[str, List[Dict[str, float]]],
                     model_id: str):
        kwargs = dict(metrics=metrics, metric_name='macro_f1')
        train_mean, train_std_err = self._get_stats(split='train', **kwargs)
        test_mean, test_std_err = self._get_stats(split='test', **kwargs)

        # Multiply scores by x100 to make them easier to read
        train_mean *= 100
        test_mean *= 100
        train_std_err *= 100
        test_std_err *= 100

        if not np.isnan(train_std_err):
            msg = (f'Mean macro-average F1-scores on AngryTweets for {model_id}:\n'
                   f'  - Train: {train_mean:.2f} +- {train_std_err:.2f}\n'
                   f'  - Test: {test_mean:.2f} +- {test_std_err:.2f}')
        else:
            msg = (f'Macro-average F1-scores on AngryTweets for {model_id}:\n'
                   f'  - Train: {train_mean:.2f}\n'
                   f'  - Test: {test_mean:.2f}')

        logger.info(msg)

    @doc_inherit
    def _get_spacy_predictions_and_labels(self,
                                          model,
                                          dataset: Dataset,
                                          progress_bar: bool) -> tuple:
        raise InvalidBenchmark('Evaluation of sentiment predictions '
                               'for SpaCy models is not yet implemented.')
