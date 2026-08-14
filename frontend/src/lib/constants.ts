// Matches the categories the Streamlit prototype's ml/data.py generates
// (and what the backend's synthetic fraud-training data uses) — keeping
// one canonical list end to end rather than free-text categories.
export const CATEGORIES = [
  'Grocery',
  'Electronics',
  'Fashion',
  'Home & Kitchen',
  'Beauty',
  'Pharmacy',
  'Food & Beverage',
  'Books',
]

// Mirrors backend/app/core/geo.py's CITY_NAMES — the fixed set of cities
// the recommendation service can compute buyer-seller distance between.
export const CITIES = [
  'Ahmedabad',
  'Bengaluru',
  'Bhopal',
  'Chandigarh',
  'Chennai',
  'Coimbatore',
  'Delhi',
  'Ghaziabad',
  'Guwahati',
  'Hyderabad',
  'Indore',
  'Jaipur',
  'Kanpur',
  'Kochi',
  'Kolkata',
  'Lucknow',
  'Mumbai',
  'Nagpur',
  'Patna',
  'Pune',
  'Surat',
  'Thane',
  'Vadodara',
  'Visakhapatnam',
]

export const PAYMENT_METHODS = ['upi', 'card', 'cod', 'wallet'] as const

export const DISPUTE_REASONS = [
  { value: 'item_not_received', label: 'Item not received' },
  { value: 'item_not_as_described', label: 'Item not as described' },
  { value: 'buyer_unresponsive', label: 'Buyer unresponsive' },
  { value: 'damaged_in_transit', label: 'Damaged in transit' },
  { value: 'other', label: 'Other' },
] as const
