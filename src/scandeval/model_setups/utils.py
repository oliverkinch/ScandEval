"""Utility functions related to setting up models."""

from typing import Any

import torch
import torch.nn as nn
from transformers import PreTrainedModel, PreTrainedTokenizer

from ..exceptions import InvalidBenchmark


def get_children_of_module(
    name: str, module: nn.Module
) -> nn.Module | dict[str, Any] | None:
    """Get the children of a module.

    Args:
        name (str):
            The name of the module.
        module (nn.Module):
            The module to get the children of.

    Returns:
        nn.Module, dict[str, Any] or None:
            The children of the module, or None if the module has no children.
    """
    if len(list(module.children())) == 0:
        if name == "token_type_embeddings":
            return module
        else:
            return None
    else:
        submodules = dict()
        for subname, submodule in module.named_children():
            children = get_children_of_module(name=subname, module=submodule)
            if children:
                submodules[subname] = children
        return submodules


def setup_model_for_question_answering(model: PreTrainedModel) -> PreTrainedModel:
    """Setup a model for question answering.

    Args:
        model (PreTrainedModel):
            The model to setup.

    Returns:
        PreTrainedModel:
            The setup model.
    """

    # Get the models' token type embedding children, if they exist
    children = get_children_of_module(name="model", module=model)

    # If the model has token type embeddings then get them
    if children:
        # Get the list of attributes that are token type embeddings
        attribute_list = list()
        done = False
        while not done:
            for key, value in children.items():
                attribute_list.append(key)
                if isinstance(value, dict):
                    children = value
                else:
                    done = True
                break

        # Get the token type embeddings
        token_type_embeddings = model
        for attribute in attribute_list:
            token_type_embeddings = getattr(token_type_embeddings, attribute)

        # If the token type embeddings has shape (1, ...) then set the shape to
        # (2, ...) by randomly initializing the second token type embedding
        if token_type_embeddings.weight.data.shape[0] == 1:
            token_type_embeddings.weight.data = torch.cat(
                (
                    token_type_embeddings.weight.data,
                    torch.rand_like(token_type_embeddings.weight.data),
                ),
                dim=0,
            )
            token_type_embeddings.num_embeddings = 2

        # Set the model config to use the new type vocab size
        model.config.type_vocab_size = 2

    return model


def align_model_and_tokenizer(
    model: PreTrainedModel, tokenizer: PreTrainedTokenizer, raise_errors: bool = False
) -> tuple[PreTrainedModel, PreTrainedTokenizer]:
    """Aligns the model and the tokenizer.

    Args:
        model (PreTrainedModel):
            The model to fix.
        tokenizer (PreTrainedTokenizer):
            The tokenizer to fix.
        raise_errors (bool, optional):
            Whether to raise errors instead of trying to fix them silently.

    Returns:
        pair of (model, tokenizer):
            The fixed model and tokenizer.
    """
    # Get all possible maximal lengths
    all_max_lengths: list[int] = []

    # Add the registered max length of the tokenizer
    if hasattr(tokenizer, "model_max_length") and tokenizer.model_max_length < 100_000:
        all_max_lengths.append(tokenizer.model_max_length)

    # Add the max length derived from the position embeddings
    if (
        hasattr(model.config, "max_position_embeddings")
        and hasattr(tokenizer, "pad_token_id")
        and tokenizer.pad_token_id is not None
    ):
        all_max_lengths.append(
            model.config.max_position_embeddings - tokenizer.pad_token_id - 1
        )

    # Add the max length derived from the model's input sizes
    if hasattr(tokenizer, "max_model_input_sizes"):
        all_max_lengths.extend(
            [
                size
                for size in tokenizer.max_model_input_sizes.values()
                if size is not None
            ]
        )

    # If any maximal lengths were found then use the shortest one
    if len(list(all_max_lengths)) > 0:
        min_max_length = min(list(all_max_lengths))
        tokenizer.model_max_length = min_max_length

    # Otherwise, use the default maximal length
    else:
        tokenizer.model_max_length = 512

    # If there is a mismatch between the vocab size according to the tokenizer and
    # the vocab size according to the model, we raise an error
    if hasattr(model.config, "vocab_size") and hasattr(tokenizer, "vocab_size"):
        if model.config.vocab_size < tokenizer.vocab_size:
            if raise_errors:
                raise InvalidBenchmark(
                    "The vocab size of the tokenizer is larger than the vocab size of "
                    "the model. As the --raise-errors option was specified, the "
                    "embeddings of the model will not be automatically adjusted."
                )
            model.resize_token_embeddings(new_num_tokens=tokenizer.vocab_size + 1)

    # If the tokenizer does not have a padding token (e.g. GPT-2), we use find a
    # suitable padding token and set it
    if tokenizer.pad_token is None:
        if tokenizer.eos_token is not None:
            tokenizer.padding_side = "left"
            tokenizer.pad_token = tokenizer.eos_token
            model.config.pad_token_id = tokenizer.pad_token_id
        elif tokenizer.sep_token is not None:
            tokenizer.padding_side = "left"
            tokenizer.pad_token = tokenizer.sep_token
            model.config.pad_token_id = tokenizer.pad_token_id
        else:
            raise InvalidBenchmark(
                "The tokenizer does not have a padding token and does not have a "
                "SEP token or EOS token to use as a padding token."
            )

    return model, tokenizer