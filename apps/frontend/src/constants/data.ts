import { NavItem } from '@/types';

export type Product = {
  photo_url: string;
  name: string;
  description: string;
  created_at: string;
  price: number;
  id: number;
  category: string;
  updated_at: string;
};

//Info: The following data is used for the sidebar navigation and Cmd K bar.
export const navItems: NavItem[] = [
  {
    title: 'Dashboard',
    url: '/dashboard/overview',
    icon: 'dashboard',
    isActive: false,
    shortcut: ['d', 'd'],
    items: [] // Empty array as there are no child items for Dashboard
  },
  {
    title: 'AI Chat',
    url: '/dashboard/ai',
    icon: 'dashboard',
    isActive: false,
    shortcut: ['d', 'd'],
    items: [] // Empty array as there are no child items for Dashboard
  },
  {
    title: 'Управление товарами',
    url: '#', // Placeholder as there is no direct link for the parent
    icon: 'product',
    shortcut: ['p', 'p'],
    isActive: false,
    items: [
      {
        title: 'Товары',
        url: '/dashboard/product',
        icon: 'package',
        shortcut: ['p', 't']
      },
      {
        title: 'Выгрузка описаний товаров',
        url: '/dashboard/product/export-descriptions',
        icon: 'download',
        shortcut: ['p', 'e']
      }
    ]
  },
  {
    title: 'Клиенты',
    url: '#',
    icon: 'user',
    isActive: false,
    items: [
      {
        title: 'Компании',
        url: '/dashboard/customers/companies',
        icon: 'user'
      },
      {
        title: 'Персоны',
        url: '/dashboard/customers/persons',
        icon: 'user'
      }
    ]
  },
  {
    title: 'Запросы цен (RFQ)',
    url: '/dashboard/rfqs',
    icon: 'billing',
    shortcut: ['r', 'f'],
    isActive: false,
    items: []
  },
  {
    title: 'Account',
    url: '#', // Placeholder as there is no direct link for the parent
    icon: 'billing',
    isActive: true,

    items: [
      {
        title: 'Profile',
        url: '/dashboard/profile',
        icon: 'userPen',
        shortcut: ['m', 'm']
      },
      {
        title: 'Login',
        shortcut: ['l', 'l'],
        url: '/',
        icon: 'login'
      }
    ]
  },
  {
    title: 'Kanban',
    url: '/dashboard/kanban',
    icon: 'kanban',
    shortcut: ['k', 'k'],
    isActive: false,
    items: [] // No child items
  },
  {
    title: 'Управление складом',
    url: '#', // Placeholder as there is no direct link for the parent
    icon: 'warehouse',
    shortcut: ['s', 't'],
    isActive: false,
    items: [
      {
        title: 'Дашборд склада',
        url: '/dashboard/stock',
        icon: 'dashboard',
        shortcut: ['s', 'd']
      },
      {
        title: 'Конкуренты',
        url: '/dashboard/stock/competitors',
        icon: 'building',
        shortcut: ['s', 'c']
      },
      {
        title: 'Товары конкурентов',
        url: '/dashboard/stock/competitor-products',
        icon: 'package',
        shortcut: ['s', 'p']
      },
      {
        title: 'Сравнение цен',
        url: '/dashboard/stock/price-comparison',
        icon: 'trendingUp',
        shortcut: ['s', 'r']
      }
    ]
  }
];

export interface SaleUser {
  id: number;
  name: string;
  email: string;
  amount: string;
  image: string;
  initials: string;
}

export const recentSalesData: SaleUser[] = [
  {
    id: 1,
    name: 'Olivia Martin',
    email: 'olivia.martin@email.com',
    amount: '+$1,999.00',
    image: 'https://api.slingacademy.com/public/sample-users/1.png',
    initials: 'OM'
  },
  {
    id: 2,
    name: 'Jackson Lee',
    email: 'jackson.lee@email.com',
    amount: '+$39.00',
    image: 'https://api.slingacademy.com/public/sample-users/2.png',
    initials: 'JL'
  },
  {
    id: 3,
    name: 'Isabella Nguyen',
    email: 'isabella.nguyen@email.com',
    amount: '+$299.00',
    image: 'https://api.slingacademy.com/public/sample-users/3.png',
    initials: 'IN'
  },
  {
    id: 4,
    name: 'William Kim',
    email: 'will@email.com',
    amount: '+$99.00',
    image: 'https://api.slingacademy.com/public/sample-users/4.png',
    initials: 'WK'
  },
  {
    id: 5,
    name: 'Sofia Davis',
    email: 'sofia.davis@email.com',
    amount: '+$39.00',
    image: 'https://api.slingacademy.com/public/sample-users/5.png',
    initials: 'SD'
  }
];
