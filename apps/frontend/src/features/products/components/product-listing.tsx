import { ProductListItem } from '@/types/products';
import { searchParamsCache } from '@/lib/searchparams';
import { ProductTable } from './product-tables';
import { columns } from './product-tables/columns';
import { fetchProductsFromBackend, searchProductsWithMeilisearch } from '@/lib/products';

type ProductListingPage = {};

export default async function ProductListingPage({ }: ProductListingPage) {
  // Showcasing the use of search params cache in nested RSCs
  const page = searchParamsCache.get('page');
  const search = searchParamsCache.get('name');
  const pageLimit = searchParamsCache.get('perPage');

  let totalProducts: number;
  let products: ProductListItem[];
  if (search) {
    const res = await searchProductsWithMeilisearch({ q: search, page, perPage: pageLimit });
    totalProducts = res.total;
    products = res.items;
  } else {
    const res = await fetchProductsFromBackend({ page, perPage: pageLimit });
    totalProducts = res.total;
    products = res.items;
  }

  return (
    <ProductTable
      data={products}
      totalItems={totalProducts}
      columns={columns}
    />
  );
}
