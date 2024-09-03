import os
import sys
import shutil
import pandas as pd
import gzip
import random
from datetime import datetime
import logging
import _pickle as cPickle
from recommenders.utils.constants import SEED

random.seed(SEED)
logger = logging.getLogger()


def data_preprocessing(
    reviews_file,
    meta_file,
    train_file,
    valid_file,
    test_file,
    user_vocab,
    item_vocab,
    cate_vocab,
    sample_rate=0.5,
    valid_num_ngs=4,
    test_num_ngs=49,
    is_history_expanding=True,
):
    """Create data for training, validation and testing from original dataset

    Args:
        reviews_file (str): Reviews dataset downloaded from former operations.
        meta_file (str): Meta dataset downloaded from former operations.
    """
    reviews_output = _reviews_preprocessing(reviews_file)
    meta_output = _meta_preprocessing(meta_file)
    instance_output = _create_instance(reviews_output, meta_output)
    _create_item2cate(instance_output)
    sampled_instance_file = _get_sampled_data(instance_output, sample_rate=sample_rate)
    preprocessed_output = _data_processing(sampled_instance_file)
    _data_generating(preprocessed_output, train_file, valid_file, test_file)
    _create_vocab(train_file, user_vocab, item_vocab, cate_vocab)
    _negative_sampling_offline(
        sampled_instance_file, valid_file, test_file, valid_num_ngs, test_num_ngs
    )



def _create_vocab(train_file, user_vocab, item_vocab, cate_vocab):

    f_train = open(train_file, "r")

    user_dict = {}
    item_dict = {}
    cat_dict = {}

    logger.info("vocab generating...")
    for line in f_train:
        arr = line.strip("\n").split("\t")
        uid = arr[1]
        pid = arr[2]
        cat = arr[3]
        pid_list = arr[5]
        cat_list = arr[6]

        if uid not in user_dict:
            user_dict[uid] = 0
        user_dict[uid] += 1
        if pid not in item_dict:
            item_dict[pid] = 0
        item_dict[pid] += 1
        if cat not in cat_dict:
            cat_dict[cat] = 0
        cat_dict[cat] += 1
        if len(pid_list) == 0:
            continue
        for m in pid_list.split(","):
            if m not in item_dict:
                item_dict[m] = 0
            item_dict[m] += 1
        for c in cat_list.split(","):
            if c not in cat_dict:
                cat_dict[c] = 0
            cat_dict[c] += 1

    sorted_user_dict = sorted(user_dict.items(), key=lambda x: x[1], reverse=True)
    sorted_item_dict = sorted(item_dict.items(), key=lambda x: x[1], reverse=True)
    sorted_cat_dict = sorted(cat_dict.items(), key=lambda x: x[1], reverse=True)

    uid_voc = {}
    index = 0
    for key, value in sorted_user_dict:
        uid_voc[key] = index
        index += 1

    pid_voc = {}
    pid_voc["default_pid"] = 0
    index = 1
    for key, value in sorted_item_dict:
        pid_voc[key] = index
        index += 1

    cat_voc = {}
    cat_voc["default_cat"] = 0
    index = 1
    for key, value in sorted_cat_dict:
        cat_voc[key] = index
        index += 1

    cPickle.dump(uid_voc, open(user_vocab, "wb"))
    cPickle.dump(pid_voc, open(item_vocab, "wb"))
    cPickle.dump(cat_voc, open(cate_vocab, "wb"))


def _negative_sampling_offline(
    instance_input_file, valid_file, test_file, valid_neg_nums=4, test_neg_nums=49
):

    columns = ["label", "UserID", "ItemID", "timestamp", "CategoryID"]
    ns_df = pd.read_csv(instance_input_file, sep="\t", names=columns)
    items_with_popular = list(ns_df["ItemID"])

    global item2cate

    # valid negative sampling
    logger.info("start valid negative sampling")
    with open(valid_file, "r") as f:
        valid_lines = f.readlines()
    write_valid = open(valid_file, "w")
    for line in valid_lines:
        write_valid.write(line)
        words = line.strip().split("\t")
        positive_item = words[2]
        count = 0
        neg_items = set()
        while count < valid_neg_nums:
            neg_item = random.choice(items_with_popular)
            if neg_item == positive_item or neg_item in neg_items:
                continue
            count += 1
            neg_items.add(neg_item)
            words[0] = "0"
            words[2] = neg_item
            words[3] = str(item2cate[neg_item])
            write_valid.write("\t".join(words) + "\n")

    # test negative sampling
    logger.info("start test negative sampling")
    with open(test_file, "r") as f:
        test_lines = f.readlines()
    write_test = open(test_file, "w")
    for line in test_lines:
        write_test.write(line)
        words = line.strip().split("\t")
        positive_item = words[2]
        count = 0
        neg_items = set()
        while count < test_neg_nums:
            neg_item = random.choice(items_with_popular)
            if neg_item == positive_item or neg_item in neg_items:
                continue
            count += 1
            neg_items.add(neg_item)
            words[0] = "0"
            words[2] = neg_item
            words[3] = str(item2cate[neg_item])
            write_test.write("\t".join(words) + "\n")


def _data_generating(input_file, train_file, valid_file, test_file, min_sequence=1):
    """produce train, valid and test file from processed_output file
    Each user's behavior sequence will be unfolded and produce multiple lines in trian file.
    Like, user's behavior sequence: 12345, and this function will write into train file:
    1, 12, 123, 1234, 12345
    """
    f_input = open(input_file, "r")
    f_train = open(train_file, "w")
    f_valid = open(valid_file, "w")
    f_test = open(test_file, "w")
    logger.info("data generating...")
    last_user_id = None
    for line in f_input:
        line_split = line.strip().split("\t")
        tfile = line_split[0]
        label = int(line_split[1])
        user_id = line_split[2]
        ItemID = line_split[3]
        date_time = line_split[4]
        category = line_split[5]

        if tfile == "train":
            fo = f_train
        elif tfile == "valid":
            fo = f_valid
        elif tfile == "test":
            fo = f_test
        if user_id != last_user_id:
            ItemID_list = []
            cate_list = []
            dt_list = []
        else:
            history_clk_num = len(ItemID_list)
            cat_str = ""
            pid_str = ""
            dt_str = ""
            for c1 in cate_list:
                cat_str += c1 + ","
            for pid in ItemID_list:
                pid_str += pid + ","
            for dt_time in dt_list:
                dt_str += dt_time + ","
            if len(cat_str) > 0:
                cat_str = cat_str[:-1]
            if len(pid_str) > 0:
                pid_str = pid_str[:-1]
            if len(dt_str) > 0:
                dt_str = dt_str[:-1]
            if history_clk_num >= min_sequence:
                fo.write(
                    line_split[1]
                    + "\t"
                    + user_id
                    + "\t"
                    + ItemID
                    + "\t"
                    + category
                    + "\t"
                    + date_time
                    + "\t"
                    + pid_str
                    + "\t"
                    + cat_str
                    + "\t"
                    + dt_str
                    + "\n"
                )
        last_user_id = user_id
        if label:
            ItemID_list.append(ItemID)
            cate_list.append(category)
            dt_list.append(date_time)


def _create_item2cate(instance_file):
    logger.info("creating item2cate dict")
    global item2cate
    instance_df = pd.read_csv(
        instance_file,
        sep="\t",
        names=["label", "UserID", "ItemID", "timestamp", "CategoryID"],
    )
    item2cate = instance_df.set_index("ItemID")["CategoryID"].to_dict()


def _get_sampled_data(instance_file, sample_rate):
    logger.info("getting sampled data...")
    global item2cate
    output_file = instance_file + "_" + str(sample_rate)
    columns = ["label", "UserID", "ItemID", "timestamp", "CategoryID"]
    ns_df = pd.read_csv(instance_file, sep="\t", names=columns)
    items_num = ns_df["ItemID"].nunique()
    items_with_popular = list(ns_df["ItemID"])
    items_sample, count = set(), 0
    while count < int(items_num * sample_rate):
        random_item = random.choice(items_with_popular)
        if random_item not in items_sample:
            items_sample.add(random_item)
            count += 1
    ns_df_sample = ns_df[ns_df["ItemID"].isin(items_sample)]
    ns_df_sample.to_csv(output_file, sep="\t", index=None, header=None)
    return output_file


def _meta_preprocessing(meta_readfile):
    logger.info("start meta preprocessing...")
    meta_writefile = meta_readfile + "_output"
    meta_r = open(meta_readfile, "r")
    meta_w = open(meta_writefile, "w")
    for line in meta_r:
        line_new = eval(line)
        meta_w.write("Item" + line_new["ItemID"] + "\t" + "Cate" + line_new["CategoryID"] + "\n")
    meta_r.close()
    meta_w.close()
    return meta_writefile


def _reviews_preprocessing(reviews_readfile):
    logger.info("start reviews preprocessing...")
    reviews_writefile = reviews_readfile + "_output"
    reviews_r = open(reviews_readfile, "r")
    reviews_w = open(reviews_writefile, "w")
    for line in reviews_r:
        line_new = eval(line.strip())
        timestamp_str = line_new['Timestamp']
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
        unix_review_time = int(timestamp.timestamp())
        reviews_w.write(
           "User" + str(line_new["UserID"])
            + "\t"
            "Item" + str(line_new["ItemID"])
            + "\t"
            + str(unix_review_time)
            + "\n"
        )
    reviews_r.close()
    reviews_w.close()
    return reviews_writefile


def _create_instance(reviews_file, meta_file):
    logger.info("start create instances...")
    dirs, _ = os.path.split(reviews_file)
    output_file = os.path.join(dirs, "instance_output")

    f_reviews = open(reviews_file, "r")
    user_dict = {}
    item_list = []
    for line in f_reviews:
        line = line.strip()
        reviews_things = line.split("\t")
        if reviews_things[0] not in user_dict:
            user_dict[reviews_things[0]] = []
        user_dict[reviews_things[0]].append((line, float(reviews_things[-1])))
        item_list.append(reviews_things[1])

    f_meta = open(meta_file, "r")
    meta_dict = {}
    for line in f_meta:
        line = line.strip()
        meta_things = line.split("\t")
        if meta_things[0] not in meta_dict:
            meta_dict[meta_things[0]] = meta_things[1]

    f_output = open(output_file, "w")
    for user_behavior in user_dict:
        sorted_user_behavior = sorted(user_dict[user_behavior], key=lambda x: x[1])
        for line, _ in sorted_user_behavior:
            user_things = line.split("\t")
            ItemID = user_things[1]
            if ItemID in meta_dict:
                f_output.write("1" + "\t" + line + "\t" + meta_dict[ItemID] + "\n")
            else:
                f_output.write("1" + "\t" + line + "\t" + "default_cat" + "\n")

    f_reviews.close()
    f_meta.close()
    f_output.close()
    return output_file


def _data_processing(input_file):
    logger.info("start data processing...")
    dirs, _ = os.path.split(input_file)
    output_file = os.path.join(dirs, "preprocessed_output")

    f_input = open(input_file, "r")
    f_output = open(output_file, "w")
    user_count = {}
    for line in f_input:
        line = line.strip()
        user = line.split("\t")[1]
        if user not in user_count:
            user_count[user] = 0
        user_count[user] += 1
    f_input.seek(0)
    i = 0
    last_user = None
    for line in f_input:
        line = line.strip()
        user = line.split("\t")[1]
        if user == last_user:
            if i < user_count[user] - 2:
                f_output.write("train" + "\t" + line + "\n")
            elif i < user_count[user] - 1:
                f_output.write("valid" + "\t" + line + "\n")
            else:
                f_output.write("test" + "\t" + line + "\n")
        else:
            last_user = user
            i = 0
            if i < user_count[user] - 2:
                f_output.write("train" + "\t" + line + "\n")
            elif i < user_count[user] - 1:
                f_output.write("valid" + "\t" + line + "\n")
            else:
                f_output.write("test" + "\t" + line + "\n")
        i += 1
    return output_file
