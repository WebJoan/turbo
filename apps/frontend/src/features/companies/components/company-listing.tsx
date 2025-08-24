import { searchParamsCache } from '@/lib/searchparams';
import { fetchCompaniesFromBackend } from '@/lib/companies';
import { CompanyTable } from './company-tables';
import { companyColumns } from './company-tables/columns';
import { CompanyListItem } from '@/types/companies';

type CompanyListingPage = {};

export default async function CompanyListingPage({ }: CompanyListingPage) {
    const page = searchParamsCache.get('page');
    const search = searchParamsCache.get('name');
    const pageLimit = searchParamsCache.get('perPage');

    const res = await fetchCompaniesFromBackend({ page, perPage: pageLimit, search });
    const companies: CompanyListItem[] = res.items;
    const totalCompanies: number = res.total;

    return (
        <CompanyTable data={companies} totalItems={totalCompanies} columns={companyColumns} />
    );
}


