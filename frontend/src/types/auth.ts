export interface User {
  id: number;
  email: string;
  phone: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  account_status?: string;
  roles: string[];
  avatar_url?: string;
  city_name?: string;
  city_id?: number;
  locality_name?: string;
  locality_id?: number;
  preferred_language?: string;
  bio?: string;
  emergency_phone?: string;
  partner_id?: number;
  partner_type?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: number;
  full_name: string;
  email: string;
  expires_in?: number;
  refresh_token?: string;
}
