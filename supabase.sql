create table if not exists public.content_drafts (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    content text not null,
    status text not null default 'draft' check (status in ('draft', 'published')),
    created_at timestamptz not null default now()
);

create table if not exists public.bookings (
    id uuid primary key default gen_random_uuid(),
    customer_name text not null,
    email text not null,
    scheduled_at timestamptz not null,
    notes text,
    status text not null default 'pending' check (status in ('pending', 'confirmed', 'cancelled')),
    created_at timestamptz not null default now()
);

create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    password_hash text not null,
    created_at timestamptz not null default now()
);

alter table public.content_drafts enable row level security;
alter table public.bookings enable row level security;
alter table public.users enable row level security;

insert into public.content_drafts (id, title, content, status) values
    ('00000000-0000-4000-8000-000000000001', 'Шинэ үйлчилгээний танилцуулга', 'Манай шинэ үйлчилгээний тухай мэдээлэл.', 'draft'),
    ('00000000-0000-4000-8000-000000000002', 'Долоо хоногийн зөвлөгөө', 'Өдөр тутмын ажилд хэрэгтэй богино зөвлөгөө.', 'draft'),
    ('00000000-0000-4000-8000-000000000003', 'Арга хэмжээний зар', 'Удахгүй болох арга хэмжээний дэлгэрэнгүй.', 'draft')
on conflict (id) do nothing;

insert into public.bookings (id, customer_name, email, scheduled_at, notes, status) values
    ('00000000-0000-4000-8000-000000000011', 'Бат', 'bat@example.com', '2026-12-01 09:00:00+08', 'Анхны уулзалт', 'pending'),
    ('00000000-0000-4000-8000-000000000012', 'Сараа', 'saraa@example.com', '2026-12-02 14:30:00+08', 'Онлайн уулзалт', 'confirmed'),
    ('00000000-0000-4000-8000-000000000013', 'Тэмүүлэн', 'temuulen@example.com', '2026-12-03 11:00:00+08', null, 'pending')
on conflict (id) do nothing;

-- Do not seed an administrator with a shared default password.
-- Insert an administrator only after generating a unique bcrypt password hash.

create table if not exists public.staff (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    email text not null unique,
    phone text,
    position text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.appointments (
    id uuid primary key default gen_random_uuid(),
    customer_name text not null,
    customer_email text not null,
    scheduled_at timestamptz not null,
    staff_id uuid references public.staff(id) on delete set null,
    notes text,
    status text not null default 'pending' check (status in ('pending', 'confirmed', 'cancelled')),
    created_at timestamptz not null default now()
);

alter table public.staff enable row level security;
alter table public.appointments enable row level security;

insert into public.staff (id, name, email, phone, position) values
    ('00000000-0000-4000-8000-000000000101', 'Номин', 'nomin@example.com', '99112233', 'Зөвлөх'),
    ('00000000-0000-4000-8000-000000000102', 'Мөнх', 'munkh@example.com', '99223344', 'Мэргэжилтэн'),
    ('00000000-0000-4000-8000-000000000103', 'Саруул', 'saruul@example.com', '99334455', 'Зөвлөх')
on conflict (id) do nothing;

insert into public.appointments (id, customer_name, customer_email, scheduled_at, staff_id, notes, status) values
    ('00000000-0000-4000-8000-000000000201', 'Бат', 'bat@example.com', '2026-12-10 10:00:00+08', '00000000-0000-4000-8000-000000000101', 'Эхний уулзалт', 'pending'),
    ('00000000-0000-4000-8000-000000000202', 'Сараа', 'saraa@example.com', '2026-12-11 14:30:00+08', '00000000-0000-4000-8000-000000000102', 'Давтан уулзалт', 'confirmed'),
    ('00000000-0000-4000-8000-000000000203', 'Тэмүүлэн', 'temuulen@example.com', '2026-12-12 11:00:00+08', '00000000-0000-4000-8000-000000000103', null, 'pending')
on conflict (id) do nothing;