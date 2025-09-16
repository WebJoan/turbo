export interface PersonListItem {
  id: number;
  ext_id: string;
  company: number;
  company_name: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  email: string;
  phone: string | null;
  position: string | null;
  department: string | null;
  status: string;
  is_primary_contact: boolean;
  created_at: string;
  updated_at: string;
}

export type PersonStatus = 'active' | 'inactive' | 'suspended';

export interface Person {
  id: number;
  ext_id: string;
  company: number;
  company_name: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  email: string;
  phone: string | null;
  position: string | null;
  department: string | null;
  status: PersonStatus;
  is_primary_contact: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  full_name: string;
}

export interface PersonCreateInput {
  company: number;
  first_name: string;
  last_name: string;
  middle_name?: string | null;
  email: string;
  phone?: string | null;
  position?: string | null;
  department?: string | null;
  status?: PersonStatus;
  is_primary_contact?: boolean;
  notes?: string | null;
}

export type PersonUpdateInput = Partial<PersonCreateInput>;


