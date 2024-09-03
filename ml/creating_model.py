import os
import sys
import mlflow
import mlflow.pyfunc
import tensorflow.compat.v1 as tf

import shutil
import pandas as pd
import random
from datetime import datetime
import logging
import _pickle as cPickle
import pickle 


from util import data_preprocessing
from recommenders.utils.timer import Timer
from recommenders.utils.constants import SEED

from SeqModelWrapper import SeqModelWrapper

from recommenders.models.deeprec.deeprec_utils import prepare_hparams
from recommenders.models.deeprec.models.sequential.sli_rec import SLI_RECModel as SeqModel
####  to use the other model, use one of the following lines:
# from recommenders.models.deeprec.models.sequential.asvd import A2SVDModel as SeqModel
# from recommenders.models.deeprec.models.sequential.caser import CaserModel as SeqModel
# from recommenders.models.deeprec.models.sequential.gru import GRUModel as SeqModel
# from recommenders.models.deeprec.models.sequential.sum import SUMModel as SeqModel
#from recommenders.models.deeprec.models.sequential.nextitnet import NextItNetModel
from recommenders.models.deeprec.io.sequential_iterator import SequentialIterator
#from recommenders.models.deeprec.io.nextitnet_iterator import NextItNetIterator
from recommenders.utils.notebook_utils import store_metadata

print(f"System version: {sys.version}")
print(f"Tensorflow version: {tf.__version__}")




random.seed(SEED)
logger = logging.getLogger()



EPOCHS = 10
BATCH_SIZE = 400
RANDOM_SEED = SEED  # Set None for non-deterministic result

data_path = os.path.join("ml","resources")

##  ATTENTION: change to the corresponding config file, e.g., caser.yaml for CaserModel, sum.yaml for SUMModel
yaml_file = 'ml/config/sli_rec.yaml'  

# for test
train_file = os.path.join(data_path, r'train_data')
valid_file = os.path.join(data_path, r'valid_data')
test_file = os.path.join(data_path, r'test_data')
user_vocab = os.path.join(data_path, r'user_vocab.pkl')
item_vocab = os.path.join(data_path, r'item_vocab.pkl')
cate_vocab = os.path.join(data_path, r'category_vocab.pkl')
output_file = os.path.join(data_path, r'output.txt')


reviews_name = 'data.json'
meta_name = 'meta_data.json'
reviews_file = os.path.join(data_path, reviews_name)
meta_file = os.path.join(data_path, meta_name)

train_num_ngs = 4 # number of negative instances with a positive instance for training
valid_num_ngs = 4 # number of negative instances with a positive instance for validation
test_num_ngs = 49 # number of negative instances with a positive instance for testing
sample_rate = 1 # sample a small item set for training and testing here for fast example

input_files = [reviews_file, meta_file, train_file, valid_file, test_file, user_vocab, item_vocab, cate_vocab]

data_preprocessing(*input_files, sample_rate=sample_rate, valid_num_ngs=valid_num_ngs, test_num_ngs=test_num_ngs)
print("data preprocessed")
hparams = prepare_hparams(yaml_file, 
                          embed_l2=0., 
                          layer_l2=0., 
                          learning_rate=0.001,  # set to 0.01 if batch normalization is disable
                          epochs=EPOCHS,
                          batch_size=BATCH_SIZE,
                          show_step=20,
                          MODEL_DIR=os.path.join(data_path, "model/"),
                          SUMMARIES_DIR=os.path.join(data_path, "summary/"),
                          user_vocab=user_vocab,
                          item_vocab=item_vocab,
                          cate_vocab=cate_vocab,
                          need_sample=True,
                          train_num_ngs=train_num_ngs, # provides the number of negative instances for each positive instance for loss computation.
            )
# Use MLflow to log parameters and training process
mlflow.start_run()

mlflow.log_param("learning_rate", hparams.learning_rate)
mlflow.log_param("epochs", hparams.epochs)


input_creator = SequentialIterator


model = SeqModel(hparams, input_creator, seed=RANDOM_SEED)


## ATTENTION: if you haven't train the model uncomment the train model part 
###
# # Train the model
# with Timer() as train_time:
#     model = model.fit(train_file, valid_file, valid_num_ngs=valid_num_ngs) 
# print(f"Training time: {train_time.interval} s")
# # Save the trained model to a specific directory
# model_dir = os.path.join(data_path, "model" , "best_model")
###

# res_syn = model.run_eval(test_file, num_ngs=test_num_ngs)
# print(res_syn)
# # Record results for tests 
# store_metadata("auc", res_syn["auc"])
# store_metadata("logloss", res_syn["logloss"])
# store_metadata("mean_mrr", res_syn["mean_mrr"])
# store_metadata("ndcg@2", res_syn["ndcg@2"])
# store_metadata("ndcg@4", res_syn["ndcg@4"])
# store_metadata("ndcg@6", res_syn["ndcg@6"])
# store_metadata("group_auc", res_syn["group_auc"])
# model = model.predict(test_file, output_file)



# load a pretrained the model
path_best_trained = os.path.join(hparams.MODEL_DIR, "best_model")
print('loading saved model in {0}'.format(path_best_trained))
model.load_model(path_best_trained)

# Defining custom PythonModel wrapper
class SeqModelWrapper(mlflow.pyfunc.PythonModel):
    
    def load_context(self, context):
        """
        This method is used to load artifacts that are needed by the model.
        """
        # Load model parameters from the artifacts path
        hparams = prepare_hparams(context.artifacts["yaml_file"])
        input_creator = SequentialIterator
        
        # Load the model from saved artifacts
        self.model = SeqModel(hparams, input_creator, seed=RANDOM_SEED)
        self.model.load_model(os.path.join('SeqModel_with_wrapper','artifacts' ,"best_model"))
    
    def convert_to_unix(self, timestamp):
        """Convert timestamp to Unix time."""
        if pd.isna(timestamp):
            return ''
        try:
            dt = pd.to_datetime(timestamp)
            dt = dt.replace(minute=0, second=0, microsecond=0)
            return int(dt.timestamp())
        except Exception as e:
            print(f"Error converting timestamp: {e}")
            return ''
        
    def process_and_write_to_file(self, model_input, filename, item_vocab_file, cate_vocab_file):
        """
        Processes the input DataFrame from the MLflow model and writes it to a file.

        :param model_input: The input DataFrame.
        :param filename: The path to the file where the data should be written.
        :param item_vocab_file: Path to the item vocabulary pickle file.
        :param cate_vocab_file: Path to the category vocabulary pickle file.
        """
        
        # Load item and category vocabularies from pickle files
        with open(item_vocab_file, 'rb') as f:
            item_voc = pickle.load(f)

        with open(cate_vocab_file, 'rb') as f:
            cate_voc = pickle.load(f)

        with open(filename, 'w') as f:
           
            # Prepare the label value
            label = 0
            
            # Extracting values 
            for _, row in model_input.iterrows():
                user_id = row['user_id']
                timestamp = row['timestamp']
                history_item_ids = row['history_item_ids']
                history_category_ids = row['history_category_ids']
                history_timestamps = row['history_timestamps']
                all_product_ids = row['all_product_ids']
                all_category_ids = row['all_category_ids']

                # Convert timestamp to Unix time
                timestamp_unix = self.convert_to_unix(timestamp)
                history_timestamps_unix = [self.convert_to_unix(ts) for ts in history_timestamps]

                # Process history item ids and category ids with vocab checks
                history_item_strs = [
                    "Item" + str(item) if "Item" + str(item) in item_voc else "default_pid"
                    for item in history_item_ids
                ]
                history_category_strs = [
                    "Cate" + str(cat) if "Cate" + str(cat) in cate_voc else "default_cat"
                    for cat in history_category_ids
                ]

                # Write rows for each product
                for item_id, category_id in zip(all_product_ids, all_category_ids):

                    item_str = "Item" + str(item_id) if "Item" + str(item_id) in item_voc else "default_pid"
                    category_str = "Cate" + str(category_id) if "Cate" + str(category_id) in cate_voc else "default_cat"
                    
                    row_data = [
                        str(label),
                        "User" + str(user_id),
                        item_str,
                        category_str,
                        str(timestamp_unix),
                        ','.join(history_item_strs), 
                        ','.join(history_category_strs), 
                        ','.join(map(str, history_timestamps_unix))  
                    ]
                    f.write('\t'.join(row_data) + '\n')


    def predict(self, context, model_input):
        """
        This method is required by mlflow.pyfunc.PythonModel. It will be used to
        generate predictions from the model.

        :param context: MLflow context 
        :param model_input: The input data for which to generate predictions
        :return: Predictions generated by the model
        """
        

        # Retrieve vocab file paths from context artifacts
        item_vocab_file = context.artifacts["item_vocab_dir"]
        cate_vocab_file = context.artifacts["cate_vocab_dir"]

        model_input = self.process_and_write_to_file(model_input , "input.txt", item_vocab_file, cate_vocab_file)
        


        self.model.predict("input.txt" , "output.txt")
        predictions = self.get_top_items("output.txt" , "input.txt")
        return predictions

    def get_top_items(self, predictions_file,items_file, top_n=10):
        """
        Get the item IDs of the top N items with the highest probabilities from the predictions file.

        :param predictions_file: Path to the file containing prediction probabilities.
        :param items_file: Path to the file containing multiple columns including item IDs.
        :param top_n: Number of top items to retrieve.
        :return: List of top item IDs.
        """
        # Read the prediction probabilities
        with open(predictions_file, 'r') as f:
            probabilities = [float(line.strip()) for line in f]

        items = []

        with open(items_file, 'r') as f:
            for line in f:
                columns = line.strip().split('\t')
                
                # Extract the item_id (3rd column, index 2)
                item_id = columns[2]
                
                # Append item details to the list (keeping the item_id and probability together)
                items.append(item_id)

        # Ensure the length of probabilities matches the number of rows in items_df
        if len(probabilities) != len(items):
            raise ValueError("The number of probabilities does not match the number of rows in items_file.")
        
        # Combine the item IDs and probabilities into a list of tuples
        item_probabilities = list(zip(items, probabilities))

        # Create a dictionary to store the probability for each item ID
        item_probability_dict = {}

        # Iterate through the list of tuples
        for item_id, probability in item_probabilities:
            if item_id in item_probability_dict:
                item_probability_dict[item_id] = max(item_probability_dict[item_id],probability)
            # If the item ID is not in the dictionary, add it with its probability
            else:
                item_probability_dict[item_id] = probability

                
        # Convert the dictionary back to a list of tuples
        combined_item_probabilities = list(item_probability_dict.items())
        # Sort the list of tuples by probability in descending order
        combined_item_probabilities.sort(key=lambda x: x[1], reverse=True)

        # Get the top N item IDs based on the sorted list
        top_items = [item_id for item_id, _ in combined_item_probabilities[:top_n]]

        return top_items
    

# Log the model using the custom PythonModel wrapper
mlflow.pyfunc.save_model(
    path="SeqModel_with_wrapper",
    python_model=SeqModelWrapper(),
    artifacts={
        "yaml_file": yaml_file,
        "item_vocab_dir": item_vocab,
        "user_vocab_dir": user_vocab,
        "cate_vocab_dir": cate_vocab,
        "best_model_data_dir": os.path.join(hparams.MODEL_DIR, "best_model.data-00000-of-00001"),
        "best_model_index_dir": os.path.join(hparams.MODEL_DIR, "best_model.index"),
        "best_model_meta_dir": os.path.join(hparams.MODEL_DIR, "best_model.meta")
    },
    conda_env={
        'name': 'sli-rec-env',
        'channels': ['defaults'],
        'dependencies': [
            'python=3.8',
            'pip',
            {
                'pip': [
                    'mlflow',
                    'pandas',
                    'microsoft-recommenders',  
                    'numpy'
                ]
            }
        ]
    }
)

mlflow.end_run()

# mlflow models serve -m SeqModel_with_wrapper --port 5000 --no-conda
