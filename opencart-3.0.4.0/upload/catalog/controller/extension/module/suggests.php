<?php
class ControllerExtensionModuleSuggests extends Controller
{
	
	public function index($setting)
	{
		$this->load->language('extension/module/suggests');

		$this->load->model('catalog/product');
		$this->load->model('tool/image');
		$this->load->model('extension/module/suggests');

		$data['products'] = array();

		if (empty($setting['limit'])) {
			$setting['limit'] = 5;
		}

		if ($this->customer->isLogged()) {
			$user_id = $this->customer->getId();
		} else {
			$user_id = null;
		}

		if (isset($this->request->get['product_id'])) {
			$product_id = (int)$this->request->get['product_id'];
		} else {
			$product_id = null;
		}

		$suggested_products = $this->model_extension_module_suggests->getSuggestedProducts($setting['limit'], $user_id, $product_id);

		foreach ($suggested_products as $product) {
			$product_info = $this->model_catalog_product->getProduct($product['product_id']);

			if ($product_info) {
				$image = $product_info['image']
					? $this->model_tool_image->resize($product_info['image'], $setting['width'], $setting['height'])
					: $this->model_tool_image->resize('placeholder.png', $setting['width'], $setting['height']);

				$price = ($this->customer->isLogged() || !$this->config->get('config_customer_price'))
					? $this->currency->format($this->tax->calculate($product_info['price'], $product_info['tax_class_id'], $this->config->get('config_tax')), $this->session->data['currency'])
					: false;

				if (!is_null($product_info['special']) && (float)$product_info['special'] >= 0) {
					$special = $this->currency->format($this->tax->calculate($product_info['special'], $product_info['tax_class_id'], $this->config->get('config_tax')), $this->session->data['currency']);
					$tax_price = (float)$product_info['special'];
				} else {
					$special = false;
					$tax_price = (float)$product_info['price'];
				}

				$tax = $this->config->get('config_tax')
					? $this->currency->format($tax_price, $this->session->data['currency'])
					: false;

				$rating = $this->config->get('config_review_status')
					? $product_info['rating']
					: false;

				$data['products'][] = array(
					'product_id'  => $product_info['product_id'],
					'thumb'       => $image,
					'name'        => $product_info['name'],
					'description' => utf8_substr(strip_tags(html_entity_decode($product_info['description'], ENT_QUOTES, 'UTF-8')), 0, $this->config->get('theme_' . $this->config->get('config_theme') . '_product_description_length')) . '..',
					'price'       => $price,
					'special'     => $special,
					'tax'         => $tax,
					'rating'      => $rating,
					'href'        => $this->url->link('product/product', 'product_id=' . $product_info['product_id'])
				);
			}
		}

		if ($data['products']) {
			return $this->load->view('extension/module/suggests', $data);
		}
	}
	private $log_file = 'system/logs/user_events.log'; 

	public function eventProductSearch($route, $args)
	{
		$user_id = $this->customer->getId();
		$search_params = $this->request->get;
		$search_params_json = json_encode($search_params);
		$this->load->model('extension/module/suggests');
		$this->model_extension_module_suggests->ProductSearch($user_id, $search_params_json);
	}

	public function eventProductView($route, $args)
	{
		$user_id = $this->customer->getId();
		$product_id = isset($this->request->get['product_id']) ? $this->request->get['product_id'] : null;
		$this->load->model('extension/module/suggests');
		$this->model_extension_module_suggests->ProductView($user_id, $product_id);
	}

	public function eventAddToCart($route, $args)
	{
		$user_id = $this->customer->getId();
		$product_id = isset($this->request->post['product_id']) ? $this->request->post['product_id'] : null;
		$this->load->model('extension/module/suggests');
		$this->model_extension_module_suggests->AddToCart($user_id, $product_id);
	}

	public function eventAddToCompare($route, $args)
	{
		$user_id = $this->customer->getId();
		$product_id = isset($this->request->post['product_id']) ? $this->request->post['product_id'] : null;
		$this->load->model('extension/module/suggests');
		$this->model_extension_module_suggests->AddToCompare($user_id, $product_id);
	}

	public function eventReviewProduct($route, $args)
	{
		$user_id = $this->customer->getId();
		$product_id = isset($this->request->get['product_id']) ? $this->request->get['product_id'] : null;
		$review_text = isset($this->request->post['text']) ? $this->request->post['text'] : null;
		$review_rating = isset($this->request->post['rating']) ? $this->request->post['rating'] : null;

		$review_data = [
			'text' => $review_text,
			'rating' => $review_rating
		];
		$this->load->model('extension/module/suggests');
		$this->model_extension_module_suggests->ReviewProduct($user_id, $product_id, $review_data);
	}

	public function eventAddToWishlist($route, $args)
	{
		$user_id = $this->customer->getId();
		$product_id = isset($this->request->post['product_id']) ? $this->request->post['product_id'] : null;
		$this->load->model('extension/module/suggests');
		$this->model_extension_module_suggests->AddToWishlist($user_id, $product_id);
	}
}
