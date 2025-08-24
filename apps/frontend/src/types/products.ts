export interface ProductListItem {
  id: number;
  ext_id: string;
  name: string;
  complex_name: string;
  brand_name: string | null;
  group_name: string | null;
  subgroup_name: string | null;
  assigned_manager: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
  } | null;
}


