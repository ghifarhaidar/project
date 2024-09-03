<?php
class ModelExtensionModuleSuggests extends Model
{


    public function getSuggestedProducts($limit = 5, $user_id = null, $product_id = null)
    {
        $product_ids = [];
        if ($user_id == null) {
            return $product_ids;
        }
        $data = [];

        $interactionQuery = $this->db->query("SELECT * FROM " . DB_PREFIX . "user_product_interactions WHERE user_id = '" . (int)$user_id . "'");


        $data = $interactionQuery->rows;



        $prediction = $this->predict($user_id, $data);
        // echo 'Prediction: ' . print_r($prediction, true);
        if ($prediction == null) {
            return $product_ids;
        }


        $num = 0;
        foreach ($prediction['predictions'] as $item) {
            if ($num == $limit) break;
            // Use preg_replace to extract the numeric part (product_id)
            $product_id = preg_replace('/[^0-9]/', '', $item);  // Remove all non-numeric characters

            // Add the extracted product_id to the $product_ids array
            $num += 1;
            $product_ids[] = [
                'product_id' => $product_id
            ];
        }

        // echo 'Prediction: ' . print_r($product_ids, true);


        return $product_ids;
    }

    private function predict($user_id, $history_data)
    {
        $current_timestamp = date("Y-m-d h:i:sa");

        // Prepare arrays to hold historical data
        $history_item_ids = [];
        $history_category_ids = [];
        $history_timestamps = [];

        usort($history_data, function ($a, $b) {
            return strtotime($a['interaction_timestamp']) - strtotime($b['interaction_timestamp']);
        });

        // Iterate through the history data to extract item IDs, category IDs, and timestamps
        foreach ($history_data as $interaction) {
            $history_item_ids[] = $interaction['product_id'];
            $history_category_ids[] = $interaction['category_id'];
            $history_timestamps[] = $interaction['interaction_timestamp'];
        }

        // Retrieve all products and their corresponding categories
        $product_query = $this->db->query("SELECT * FROM " . DB_PREFIX . "product_to_category ");
        $products = $product_query->rows;

        // Prepare arrays to hold all product IDs and their corresponding category IDs
        $all_product_ids = [];
        $all_category_ids = [];
        $unique_product_categories = [];

        foreach ($products as $product) {

            $product_id = $product['product_id'];
            $category_id = $product['category_id'];

            if (!isset($unique_product_categories[$product_id])) {
                $unique_product_categories[$product_id] = $category_id;
                $all_product_ids[] = $product['product_id'];
                $all_category_ids[] = $product['category_id'];
            }
        }

        // Prepare the JSON payload for the request using `dataframe_split` format
        $data = json_encode(array(
            'dataframe_split' => array(
                'columns' => [
                    'user_id', 'timestamp',
                    'history_item_ids', 'history_category_ids', 'history_timestamps',
                    'all_product_ids', 'all_category_ids'
                ],
                'data' => [[
                    $user_id,                           // Current user ID
                    $current_timestamp,                 // Current timestamp
                    $history_item_ids,                  // List of historical item IDs
                    $history_category_ids,              // List of historical category IDs
                    $history_timestamps,                 // List of historical timestamps
                    $all_product_ids,                   // List of all product IDs
                    $all_category_ids                   // List of all category IDs
                ]]
            )
        ));

        $url = 'http://127.0.0.1:5000/invocations';  // MLflow model server endpoint

        // Initialize cURL session
        $ch = curl_init($url);

        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array(
            'Content-Type: application/json'
        ));
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $data);

        // Execute cURL request and get the response
        $response = curl_exec($ch);
        if (curl_errno($ch)) {
            // echo 'cURL error: ' . curl_error($ch);
            curl_close($ch);
            return null;
        }

        curl_close($ch);

        return json_decode($response, true);
    }




    public function ProductSearch($user_id, $search_params_json)
    {
    }
    public function ProductView($user_id, $product_id)
    {
        // Disable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 0");

        // Retrieve the category_id for the product
        $category_query = $this->db->query("SELECT category_id FROM " . DB_PREFIX . "product_to_category WHERE product_id = " . (int)$product_id);

        if ($category_query->num_rows > 0) {
            $category_id = (int)$category_query->row['category_id'];
        } else {
            $category_id = 0;
        }

        $interaction_type = 'view';
        $interaction_timestamp = date('Y-m-d H:i:00');

        // Insert interaction data into the table
        $this->db->query("INSERT INTO " . DB_PREFIX . "user_product_interactions (user_id, product_id, category_id, interaction_timestamp, interaction_type) VALUES ('" . (int)$user_id . "', '" . (int)$product_id . "', '" . (int)$category_id . "', '" . $interaction_timestamp . "', '" . $interaction_type . "')");

        // Re-enable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 1");
    }

    public function AddToCart($user_id, $product_id)
    {
        // Disable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 0");

        // Retrieve the category_id for the product
        $category_query = $this->db->query("SELECT category_id FROM " . DB_PREFIX . "product_to_category WHERE product_id = " . (int)$product_id);

        if ($category_query->num_rows > 0) {
            $category_id = (int)$category_query->row['category_id'];
        } else {
            $category_id = 0;
        }

        $interaction_type = 'add_to_cart';
        $interaction_timestamp = date('Y-m-d H:i:00');

        // Insert interaction data into the table
        $this->db->query("INSERT INTO " . DB_PREFIX . "user_product_interactions (user_id, product_id, category_id, interaction_timestamp, interaction_type) VALUES ('" . (int)$user_id . "', '" . (int)$product_id . "', '" . (int)$category_id . "', '" . $interaction_timestamp . "', '" . $interaction_type . "')");

        // Re-enable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 1");
    }

    public function AddToCompare($user_id, $product_id)
    {
        // Disable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 0");

        // Retrieve the category_id for the product
        $category_query = $this->db->query("SELECT category_id FROM " . DB_PREFIX . "product_to_category WHERE product_id = " . (int)$product_id);

        if ($category_query->num_rows > 0) {
            $category_id = (int)$category_query->row['category_id'];
        } else {
            $category_id = 0;
        }

        $interaction_type = 'add_to_compare';
        $interaction_timestamp = date('Y-m-d H:i:00');

        // Insert interaction data into the table
        $this->db->query("INSERT INTO " . DB_PREFIX . "user_product_interactions (user_id, product_id, category_id, interaction_timestamp, interaction_type) VALUES ('" . (int)$user_id . "', '" . (int)$product_id . "', '" . (int)$category_id . "', '" . $interaction_timestamp . "', '" . $interaction_type . "')");

        // Re-enable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 1");
    }

    public function ReviewProduct($user_id, $product_id, $review_data)
    {
        // Disable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 0");

        // Retrieve the category_id for the product
        $category_query = $this->db->query("SELECT category_id FROM " . DB_PREFIX . "product_to_category WHERE product_id = " . (int)$product_id);

        if ($category_query->num_rows > 0) {
            $category_id = (int)$category_query->row['category_id'];
        } else {
            $category_id = 0;
        }

        $interaction_type = 'review_product';
        $interaction_timestamp = date('Y-m-d H:i:00');

        // Insert interaction data into the table
        $this->db->query("INSERT INTO " . DB_PREFIX . "user_product_interactions (user_id, product_id, category_id, interaction_timestamp, interaction_type) VALUES ('" . (int)$user_id . "', '" . (int)$product_id . "', '" . (int)$category_id . "', '" . $interaction_timestamp . "', '" . $interaction_type . "')");

        // Re-enable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 1");
    }

    public function AddToWishlist($user_id, $product_id)
    {
        // Disable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 0");

        // Retrieve the category_id for the product
        $category_query = $this->db->query("SELECT category_id FROM " . DB_PREFIX . "product_to_category WHERE product_id = " . (int)$product_id);

        if ($category_query->num_rows > 0) {
            $category_id = (int)$category_query->row['category_id'];
        } else {
            $category_id = 0;
        }

        $interaction_type = 'add_to_wishlist';
        $interaction_timestamp = date('Y-m-d H:i:00');

        // Insert interaction data into the table
        $this->db->query("INSERT INTO " . DB_PREFIX . "user_product_interactions (user_id, product_id, category_id, interaction_timestamp, interaction_type) VALUES ('" . (int)$user_id . "', '" . (int)$product_id . "', '" . (int)$category_id . "', '" . $interaction_timestamp . "', '" . $interaction_type . "')");

        // Re-enable foreign key checks
        $this->db->query("SET FOREIGN_KEY_CHECKS = 1");
    }
}
