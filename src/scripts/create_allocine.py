"""Create the Allocine-mini sentiment dataset and upload it to the HF Hub."""

import pandas as pd
from datasets import Dataset, DatasetDict, Split, load_dataset
from huggingface_hub import HfApi
from requests import HTTPError


def main() -> None:
    """Create the Allocine-mini sentiment dataset and upload it to the HF Hub."""
    # Define the base download URL
    repo_id = "tblard/allocine"

    # Download the dataset
    dataset = load_dataset(path=repo_id, token=True)
    assert isinstance(dataset, DatasetDict)

    # Convert the dataset to a dataframe
    train_df = dataset["train"].to_pandas()
    val_df = dataset["validation"].to_pandas()
    test_df = dataset["test"].to_pandas()
    assert isinstance(train_df, pd.DataFrame)
    assert isinstance(val_df, pd.DataFrame)
    assert isinstance(test_df, pd.DataFrame)

    # Rename `review` to `text`
    train_df.rename(columns={"review": "text"}, inplace=True)
    val_df.rename(columns={"review": "text"}, inplace=True)
    test_df.rename(columns={"review": "text"}, inplace=True)

    # Convert labels to text
    label_mapping = {0: "negative", 1: "positive"}
    train_df["label"] = train_df["label"].map(lambda x: label_mapping[int(x)])
    val_df["label"] = val_df["label"].map(lambda x: label_mapping[int(x)])
    test_df["label"] = test_df["label"].map(lambda x: label_mapping[int(x)])

    # Create validation split
    val_size = 256
    val_df = val_df.sample(n=val_size, random_state=4242)

    # Create test split
    test_size = 2048
    test_df = test_df.sample(n=test_size, random_state=4242)

    # Create train split
    train_size = 1024
    train_df = train_df.sample(n=train_size, random_state=4242)

    # Reset the index
    train_df = train_df.reset_index(drop=True)
    val_df = val_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)

    # Collect datasets in a dataset dictionary
    dataset = DatasetDict(
        train=Dataset.from_pandas(train_df, split=Split.TRAIN),
        val=Dataset.from_pandas(val_df, split=Split.VALIDATION),
        test=Dataset.from_pandas(test_df, split=Split.TEST),
    )

    # Create dataset ID
    dataset_id = "ScandEval/allocine-mini"

    # Remove the dataset from Hugging Face Hub if it already exists
    try:
        api = HfApi()
        api.delete_repo(dataset_id, repo_type="dataset")
    except HTTPError:
        pass

    # Push the dataset to the Hugging Face Hub
    dataset.push_to_hub(dataset_id, private=True)


if __name__ == "__main__":
    main()