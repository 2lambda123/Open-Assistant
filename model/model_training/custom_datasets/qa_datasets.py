"""
Open / close book QA datasets
"""

import glob
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import numpy as np
from datasets import load_dataset
from model_training.custom_datasets.utils import _filter_by_words
from torch import Generator
from torch.utils.data import Dataset, Subset, random_split

# @agoryuno contributed this
re_reference_remove = re.compile(r"\[\d+(?:,\s*\d+)*?\]")


def index_squad_v2(example):
    if len(example["answers"]["text"]):
        answer = example["answers"]["text"][0]
    else:
        answer = "I do not have answer for that"
    return example["context"] + " " + example["question"], answer


def index_uasquad(example):
    if len(example["Answer"]):
        answer = example["Answer"]
    else:
        answer = "Я не маю на це відповіді"
    return example["Context"] + " " + example["Question"], answer


def index_trivia_qa_nocontext(example):
    # dummy return one randomly
    return example["question"], example["answer"]["aliases"][np.random.randint(len(example["answer"]["aliases"]))]


def index_trivia_qa_context(example):
    question = example["question"]
    if len(example["search_results"]["search_context"]):
        context = example["search_results"]["search_context"][
            np.random.randint(len(example["search_results"]["search_context"]))
        ]
    else:
        context = ""
    answer = example["answer"]["aliases"][np.random.randint(len(example["answer"]["aliases"]))]

    return context + " " + question, answer


def index_adversarial_qa(example):
    return example["title"] + ". " + example["context"] + " " + example["question"], example["answers"]["text"][0]


def index_gsm8k(example):
    return example["question"], example["answer"]


def index_wikihow(example):
    return example["title"] + ", explain step by step", example["result"]


def index_essay_instruction(example):
    return example["instructions"], example["titles"].strip() + "\n" + example["essays"]


def index_math_qa(example):
    """
    we are not including choices, so no need to output the "answer : <a,b,c,d>" part
    > if girls is 10 and boys is 20 , then 10 / 20 . so ratio of girls to boys is = 10 / 20 = 1 / 2 answer : a
    """
    return example["Problem"], example["Rationale"].split("answer : ", maxsplit=1)[0]


def index_eli5(example):
    return example["title"], example["answers"]["text"][0]


def index_gsm_hard(example):
    return example[
        "input"
    ] + "\nWrite a small snippet of python code to answer this", "Here's the code solution to the question\n```python\n{}\n```\n The answer should be {}".format(
        example["code"].strip(), example["target"]
    )


class QADataset(Dataset):
    """
    How to define a new QA dataset:

    Criteria : the qa dataset doesn't need fancy transform needed between fields rows or list

    1. Write the transform function, which maps each row into a pair of (question, answer) tuple

    2. Update DATASET_FORMAT_MAPPING with your dataset name and required parameter

        - index_fn : your transform function

        - name: the dataset name, this will be used when the name is different than huggingface load_dataset name

        - params: if your dataset require a predefined name, create a dictionary with the parameter name-value dictionary

    Feel free to create issues on GH for any suggestion how we can simplify this thing
    """

    DATASET_FORMAT_MAPPING = {
        "squad_v2": {"index_fn": index_squad_v2},
        "ua_squad": {
            "index_fn": index_uasquad,
            "name": "FIdo-AI/ua-squad",
            "params": {"field": "data"},
            "no_val": True,
        },
        "trivia_qa_nocontext": {
            "index_fn": index_trivia_qa_nocontext,
            "name": "trivia_qa",
            "params": {"name": "rc.nocontext"},
        },
        "trivia_qa_context": {"index_fn": index_trivia_qa_context, "name": "trivia_qa", "params": {"name": "rc"}},
        "adversarial_qa": {
            "index_fn": index_adversarial_qa,
            "params": {"name": "adversarialQA"},
        },
        "gsm8k_hard": {"index_fn": index_gsm_hard, "name": "reasoning-machines/gsm-hard", "no_val": True},
        "gsm8k": {"index_fn": index_gsm8k, "params": {"name": "main"}, "validation": "test"},
        "wikihow": {"name": "b-mc2/wikihow_lists", "index_fn": index_wikihow, "no_val": True},
        "essay_instruction": {
            "name": "ChristophSchuhmann/essays-with-instructions",
            "index_fn": index_essay_instruction,
            "no_val": True,
        },
        "math_qa": {
            "index_fn": index_math_qa,
        },
        "reddit_eli5": {"name": "eli5", "index_fn": index_eli5, "split_postfix": "_eli5"},
        "reddit_askh": {"name": "eli5", "index_fn": index_eli5, "split_postfix": "_askh"},
        "reddit_asks": {"name": "eli5", "index_fn": index_eli5, "split_postfix": "_asks"},
    }

    def __init__(self, dataset, cache_dir, split):
        self.no_val = False
        if dataset in self.DATASET_FORMAT_MAPPING:
            context = self.DATASET_FORMAT_MAPPING[dataset]
            if split == "validation" and "validation" in context:
                split = context["validation"]
            if "name" not in context:
                context["name"] = dataset
            if "split_postfix" in context:
                # append a postfix to split name, used in eli5 : test_eli5, test_asks, test_askh
                split += context["split_postfix"]
            if "params" not in context:
                context["params"] = {"cache_dir": cache_dir, "split": split}
            else:
                context["params"]["cache_dir"] = cache_dir
                context["params"]["split"] = split
            if "no_val" in context:
                self.no_val = True
            self.index_fn = context["index_fn"]
            self.dataset = load_dataset(context["name"], **context["params"])
        else:
            raise ValueError("Unknown dataset : " + dataset)
        self.length = len(self.dataset)

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        data = self.dataset[idx]
        return self.index_fn(data)


class WebGPT(Dataset):
    name = "webgpt"

    def __init__(self, mode: str = "sft", max_answers: int = 5) -> None:
        super().__init__()
        self.mode = mode
        assert mode in ("sft", "rm", "rl")

        dataset = load_dataset("openai/webgpt_comparisons")

        self.questions = []
        self.answers = []

        question_answer_dict = defaultdict(dict)

        for row in dataset["train"]:
            question = row["question"]["full_text"]
            answer_0 = re_reference_remove.sub("", row["answer_0"])
            answer_1 = re_reference_remove.sub("", row["answer_1"])
            if answer_0 != "" and answer_1 != "" and answer_0 != answer_1:
                question_answer_dict[question][answer_0] = row["score_0"]
                question_answer_dict[question][answer_1] = row["score_1"]

        for question, answers in question_answer_dict.items():
            self.questions.append(question)
            # Sort answer dict with the highest score first (hence the prefactor -1).
            # Then take only the first `max_answers` elements (usually there are just
            # 2, but there are examples where we have more)
            answers_sorted = [x[0] for x in sorted(answers.items(), key=lambda x: -1 * x[1])]
            self.answers.append(answers_sorted[:max_answers])

    def __len__(self) -> int:
        return len(self.questions)

    def __getitem__(self, index) -> list[str] | tuple[list[str], list[str]]:
        question = self.questions[index]
        answers = self.answers[index]
        if self.mode == "sft":
            return [question, answers[0]]
        elif self.mode == "rm":
            return ([question], answers)
        elif self.mode == "rl":
            return (question,)


class SODA(Dataset):
    name = "soda"

    def process_soda_convo(self, data: dict[str, Any], input_max_length: int) -> list[list[str]] | None:
        play_as = data["speakers"][1]
        dialogue_bg = "{}{}".format(
            # QA_SPECIAL_TOKENS["StartPrefix"],
            data["narrative"],
            " You are {}.".format(play_as),
            # QA_SPECIAL_TOKENS["EndPrefix"],
        )

        # Perform some sanity checks, if these fail return None
        # ignore data with more than 2 speakers for now
        if len(set(data["speakers"])) != 2:
            return None
        speaker1 = data["speakers"][0]
        speaker2 = data["speakers"][1]
        # make sure that the speakers are in correct order [S1, S2, S1, S2, S1, S2], otherwise return None
        speaker1_idx = [idx % 2 == 0 for idx, k in enumerate(data["speakers"]) if k == speaker1]
        speaker2_idx = [idx % 2 == 1 for idx, k in enumerate(data["speakers"]) if k == speaker2]
        if all(speaker1_idx) and all(speaker2_idx):
            # add dialog background to first question.
            # [Q1, A1, Q2, A2] -> [B + Q1, A1, Q2, A2]
            data["dialogue"][0] = f"{dialogue_bg} {data['dialogue'][0]}"
            # Use only input_max_length characters
            truncated_dialogue = [k[:input_max_length] for k in data["dialogue"]]
            return truncated_dialogue

    def __init__(self, cache_dir, mode="sft", input_max_length=1024) -> None:
        super().__init__()
        if mode not in ("sft", "rl"):
            raise NotImplementedError(f"Currently only the modes 'sft' and 'rl' are implemented. Received {mode}.")
        self.mode = mode
        self.pairs = []
        dataset = load_dataset("allenai/soda", cache_dir=cache_dir)["train"]
        for data in dataset:
            if (processed_data := self.process_soda_convo(data, input_max_length=input_max_length)) is not None:
                self.pairs.append(processed_data)
            # for prompt, answer in data_pair:
            #     if len(prompt) < input_max_length:
            #         self.pairs.append((prompt, answer))

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, index) -> list[str] | tuple[str]:
        # special token added during preprocess
        if self.mode == "sft":
            return self.pairs[index]
        elif self.mode == "rl":
            # add prefix + first human question
            return (self.pairs[index][0] + " " + self.pairs[index][1],)


class SODADialogue(Dataset):
    def __init__(self, cache_dir, verbose=True):
        dataset = load_dataset("emozilla/soda_synthetic_dialogue", cache_dir=cache_dir)

        self.pairs = []
        faulty = 0
        for split in dataset:
            for row in dataset[split]:
                question_answer_pairs = ()

                question_answers = row["conversation"].split("User: ")
                for question_answer in question_answers[1:]:  # first element is empty
                    try:
                        question, answer = question_answer.split("\nAssistant: ")
                        question_answer_pairs += (
                            question,
                            answer,
                        )
                    except ValueError:
                        # there might be some extra 'User: ' or 'Assistant: ' tokens in the dataset that cause trouble..
                        faulty += 1
                        continue

                self.pairs.append(question_answer_pairs)

        if verbose:
            print("For SODA dialogue dataset found {} faults within the total {} dialogs".format(faulty, len(self)))

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, index):
        return self.pairs[index]


class JokeExplaination(Dataset):
    name = "joke"
    url = "https://gist.github.com/theblackcat102/42b697e24a13fdb499e20edfbf618361/raw/1834dca207898c15f93b809d1195f6f6e47c9e1e/joke_explained.jsonl"

    def __init__(self, cache_dir) -> None:
        super().__init__()
        os.makedirs(cache_dir, exist_ok=True)
        joke_explain_filename = os.path.join(cache_dir, "joke_explaination.jsonl")
        if not os.path.exists(joke_explain_filename):
            with urlopen(self.url) as file:
                content = file.read().decode()
            with open(joke_explain_filename, "w") as fout:
                fout.write(content)

        question = ""
        answer = ""
        self.pairs = []
        with open(joke_explain_filename, "r") as f:
            for line in f:
                data = json.loads(line)
                joke = data["joke"]
                # DO NOT change this
                # its the data that had syntax error
                explanation = data["explaination"]
                self.pairs.append((joke, explanation))

        if len(question) > 0 and len(answer) > 0:
            self.pairs.append((question, answer))
        self.length = len(self.pairs)

    def __len__(self):
        return self.length

    def __getitem__(self, index):
        return self.pairs[index]


class TranslatedQA(Dataset):
    """
    Translation OA v3 results
    a list of non english translation of OA v3 instruction generated text in jsonl
    format for each line:
    {
        "text": "User: ... Assistant: ....",
        "meta": {"source": ... },
        "translate": [
            { "round": 1, "human":"...", "answer": "..."},
            ...
            { "round": K, "human":"...", "answer": "..."},
        ]
    }
    Since OA contain some code we needed to reference the original text to skip these
    """

    name = "oa_translated"

    def __init__(self, cache_dir) -> None:
        super().__init__()
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, self.name)
        os.makedirs(path, exist_ok=True)
        self.pairs = []
        for translated_jsonl in glob.glob(os.path.join(path, "*.jsonl")):
            with open(translated_jsonl, "r") as fin:
                for line in fin:
                    data = json.loads(line)
                    if "Python " in data["text"]:
                        # translation currently doesn't ignore code
                        # so we will have to reference original text
                        # for ignoring the translation
                        continue
                    prefix = ""
                    for convo_round in data["translate"]:
                        human, answer = convo_round["human"], convo_round["answer"]
                        if convo_round["round"] > 2:
                            self.pairs.append((prefix, human, answer))
                        else:
                            self.pairs.append(("", human, answer))

                        # Does this make sense?
                        prefix += "{}{}{}{}".format(
                            "Question:",
                            convo_round["human"],
                            "Answer:",
                            convo_round["answer"],
                        )

        self.length = len(self.pairs)

    def __len__(self):
        return self.length

    def __getitem__(self, index):
        return self.pairs[index]


class AlpacaBaseDataset(Dataset):
    def __init__(self, data: list, mode: str):
        super().__init__()
        self.data = data
        if mode not in ("sft", "rl"):
            raise NotImplementedError(
                f"Alpaca Dataset for mode {self.mode} is not implemented. Currently supported modes are 'sft' and 'rl'."
            )
        self.mode = mode

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        question, answer = self.data[index]
        if self.mode == "sft":
            return (question, answer)
        elif self.mode == "rl":
            return (question,)


def load_alpaca_dataset(
    dataset_name: str,
    val_split: float,
    cache_dir: str,
    mode: str = "sft",
    manual_seed: int = 287631038922,
    reverse_augmentation: bool = False,
    keep_unreversed: bool = True,
) -> tuple[AlpacaBaseDataset, AlpacaBaseDataset]:
    generator = Generator()
    generator.manual_seed(manual_seed)

    def process_split(
        dataset: Subset, reverse_augmentation: bool = False, keep_unreversed: bool = True
    ) -> list[tuple[str, str]]:
        data = []
        for row in dataset:
            question = row["instruction"]
            if len(row["input"]) > 0:
                input_ = "{}\n{}".format(question, row["input"])
            else:
                input_ = question
            if (_filter_by_words(input_) is None) or (_filter_by_words(row["output"]) is None):
                continue
            if reverse_augmentation:
                data.append((row["output"], input_))
                # in case of reverse augmentation we just keep both, reversed and unreversed data
                if keep_unreversed:
                    data.append((input_, row["output"]))
            else:
                data.append((input_, row["output"]))
        return data

    if dataset_name == "alpaca":
        dataset = load_dataset("yahma/alpaca-cleaned", cache_dir=cache_dir)
    elif dataset_name == "code_alpaca":
        dataset = load_dataset("sahil2801/CodeAlpaca-20k", cache_dir=cache_dir)
    else:
        raise ValueError(f"Expected dataset_name to be 'alapaca' or 'code_alpaca'. Received {dataset_name}.")

    splits = random_split(dataset["train"], lengths=[1.0 - val_split, val_split], generator=generator)
    train = AlpacaBaseDataset(
        process_split(splits[0], reverse_augmentation=reverse_augmentation, keep_unreversed=keep_unreversed), mode=mode
    )
    val = AlpacaBaseDataset(
        process_split(splits[1], reverse_augmentation=False, keep_unreversed=keep_unreversed), mode=mode
    )
    return train, val


class Vicuna(Dataset):
    name = "vicuna"

    @staticmethod
    def process_vicuna_conversations(data: list[dict[str, None | str]], input_max_length: int) -> list[str] | None:
        dialogue = []
        role = None
        messages = []
        # drop conversations that start with Bot
        if len(data["conversations"]) == 0 or data["conversations"][0]["from"] != "human":
            return None
        for line in data["conversations"]:
            speaker = line["from"]  # 'human' or 'gpt'
            message = line["value"]

            # remove markdown escaping in revision 192ab2185289094fc556ec8ce5ce1e8e587154ca
            # python-markdownify with escape_asterisks & escape_underscores True is used
            # for pre-processing the dataset.
            # See also https://github.com/LAION-AI/Open-Assistant/issues/2510
            message = message.replace(r"\_", "_")
            message = message.replace(r"\*", "*")

            if role != speaker:
                if role is not None:
                    dialogue.append("\n".join(messages))
                    messages = []
                role = speaker
            messages.append(message.strip())

        if role is not None and len(messages) > 0:
            dialogue.append("\n".join(messages))
        dialogue_truncated = [k[:input_max_length] for k in dialogue]
        return dialogue_truncated

    def __init__(self, cache_dir: str | Path, mode: str = "sft", input_max_length: int = 2048) -> None:
        super().__init__()

        self.pairs = []
        if mode not in ("sft", "rl"):
            raise NotImplementedError(f"Currently only the modes 'sft' and 'rl' are implemented. Received {mode}.")
        self.mode = mode
        dataset = load_dataset(
            "anon8231489123/ShareGPT_Vicuna_unfiltered",
            cache_dir=cache_dir,
            data_files=["ShareGPT_V3_unfiltered_cleaned_split_no_imsorry.json"],
            revision="192ab2185289094fc556ec8ce5ce1e8e587154ca",
        )["train"]
        for data in dataset:
            if (
                processed_data := self.process_vicuna_conversations(data, input_max_length=input_max_length)
            ) is not None:
                self.pairs.append(processed_data)

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, index: int) -> list[str] | tuple[str]:
        dialogue: list[str] = self.pairs[index]
        if self.mode == "sft":
            return dialogue
        elif self.mode == "rl":
            return tuple(dialogue[:-1])


class DatabricksDolly15k(Dataset):
    def __init__(self, cache_dir: str | Path, mode: str = "sft", input_max_length: int = 2048) -> None:
        super().__init__()
        self.rows = []
        self.citation_regex = re.compile(r"\[[a-zA-Z]\]")  # removes citations in the form of e.g. [a] or [A]
        if mode not in ("sft", "rl"):
            raise NotImplementedError(f"Currently only the modes 'sft' and 'rl' are implemented. Received {mode}.")
        self.mode = mode
        data = load_dataset("OllieStanley/oa_dolly_15k", cache_dir=cache_dir)
        for line in data["train"]:
            if (conv := self._process_instruction(line, input_max_length)) is not None:
                self.rows.append(conv)

    def _process_instruction(self, row: dict[str, str], input_max_length: int) -> list[str] | None:
        if context := re_reference_remove.sub("", row["METADATA"]["CONTEXT"]):
            # further remove references
            context = context.replace("[citation needed]", "")
            context = self.citation_regex.sub("", context)
            return [f"{context} {row['INSTRUCTION']}"[:input_max_length], row["RESPONSE"][:input_max_length]]
        else:
            return [row["INSTRUCTION"][:input_max_length], row["RESPONSE"][:input_max_length]]

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> list[str] | tuple[str]:
        dialogue: list[str] = self.rows[index]
        if self.mode == "sft":
            return dialogue
        elif self.mode == "rl":
            return tuple(dialogue[:-1])
