import { searchParamsCache } from '@/lib/searchparams';
import { fetchCompaniesFromBackend } from '@/lib/companies';
import { CompanyTable } from './company-tables';
import { companyColumns } from './company-tables/columns';
import { CompanyListItem } from '@/types/companies';

type CompanyListingPage = { searchParams?: Record<string, string | string[] | undefined> };

export default async function CompanyListingPage({ searchParams }: CompanyListingPage) {
    const { page, name: search, perPage: pageLimit } = searchParamsCache.parse(searchParams || {});

    const res = await fetchCompaniesFromBackend({ page, perPage: pageLimit, search });
    const companies: CompanyListItem[] = res.items;
    const totalCompanies: number = res.total;

    return (
        <CompanyTable data={companies} totalItems={totalCompanies} columns={companyColumns} />
    );
}


