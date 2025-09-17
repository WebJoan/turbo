import { ProductListItem } from '@/types/products';
import { searchParamsCache } from '@/lib/searchparams';
import { ProductTable } from './product-tables';
import { columns } from './product-tables/columns';
import { fetchProductsFromBackend, searchProductsWithMeilisearch } from '@/lib/products';

type ProductListingPage = { searchParams?: Record<string, string | string[] | undefined> };

export default async function ProductListingPage({ searchParams }: ProductListingPage) {
  const { page, name: search, perPage: pageLimit } = searchParamsCache.parse(searchParams || {});

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
