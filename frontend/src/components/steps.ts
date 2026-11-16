/** What each backend tool does, in the visitor's words. */
export const STEP_LABEL: Record<string, string> = {
  search_products: 'Searched the catalog',
  describe_catalog: 'Read the spec list',
  get_product: 'Looked up a product',
  compare_products: 'Compared models',
  check_availability: 'Checked availability',
  find_compatible: 'Found compatible accessories',
}

export const STEP_PROGRESS: Record<string, string> = {
  search_products: 'Searching the catalog',
  describe_catalog: 'Reading the spec list',
  get_product: 'Looking up the product',
  compare_products: 'Comparing models',
  check_availability: 'Checking availability',
  find_compatible: 'Finding compatible accessories',
}
