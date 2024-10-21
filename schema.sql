create table
  public.cart_items (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    sku text not null,
    potion_quantity integer null,
    cart_id bigint null,
    constraint cart_items_pkey primary key (id),
    constraint cart_items_cart_id_fkey foreign key (cart_id) references carts (id) on update cascade on delete cascade
  ) tablespace pg_default;

  create table
  public.carts (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    customer_id bigint null,
    constraint carts_pkey primary key (id),
    constraint carts_customer_id_fkey foreign key (customer_id) references customers (id)
  ) tablespace pg_default;

  create table
  public.customer_purchases (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    customer_id bigint null,
    gold_cost integer null,
    transaction_id bigint null,
    cart_id bigint null,
    time_id bigint null,
    constraint order_pkey primary key (id),
    constraint customer_ledgers_time_id_fkey foreign key (time_id) references "time" (id),
    constraint order_ledgers_transaction_id_fkey foreign key (transaction_id) references transactions (id)
  ) tablespace pg_default;

  create table
  public.customer_visits (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    customer_id bigint null,
    visit_id bigint null,
    time_id bigint null,
    constraint visit_pkey primary key (id)
  ) tablespace pg_default;

  create table
  public.customers (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    level bigint null,
    customer_name text null,
    customer_class text null,
    constraint customers_pkey primary key (id)
  ) tablespace pg_default;

  create table
  public.global_inventory (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    gold bigint null,
    num_green_ml bigint null,
    num_potions bigint null,
    num_red_ml bigint null,
    num_blue_ml bigint null,
    num_dark_ml bigint null,
    ml_capacity integer null,
    potion_capacity integer null,
    constraint global_inventory_pkey primary key (id)
  ) tablespace pg_default;

  create table
  public.gold_ledgers (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    time_id bigint null,
    gold bigint null,
    transaction_id bigint null,
    constraint gold_ledgers_pkey primary key (id),
    constraint gold_ledgers_time_id_fkey foreign key (time_id) references "time" (id),
    constraint gold_ledgers_transaction_id_fkey foreign key (transaction_id) references transactions (id)
  ) tablespace pg_default;

  create table
  public.ml_ledgers (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    num_red_ml bigint null,
    num_green_ml bigint null,
    num_blue_ml bigint null,
    num_dark_ml bigint null,
    order_id bigint null,
    time_id bigint null,
    transaction_id bigint null,
    constraint ml_ledgers_pkey primary key (id),
    constraint ml_ledgers_time_id_fkey foreign key (time_id) references "time" (id),
    constraint ml_ledgers_transaction_id_fkey foreign key (transaction_id) references transactions (id)
  ) tablespace pg_default;

  create table
  public.potion_ledgers (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    sku text null,
    quantity double precision null,
    time_id bigint null,
    transaction_id bigint null,
    order_id bigint null,
    constraint potion_ledgers_pkey primary key (id),
    constraint potion_ledgers_time_id_fkey foreign key (time_id) references "time" (id),
    constraint potion_ledgers_transaction_id_fkey foreign key (transaction_id) references transactions (id)
  ) tablespace pg_default;

  create table
  public.potions (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    sku text not null,
    red integer null,
    green integer null,
    blue integer null,
    dark integer null,
    name text null default ''::text,
    quantity bigint null,
    price bigint null,
    brew boolean not null default false,
    constraint potions_replacement_pkey primary key (id),
    constraint potions_replacement_sku_key unique (sku)
  ) tablespace pg_default;

  create table
  public.time (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    hour bigint null,
    day text null,
    constraint time_pkey primary key (id)
  ) tablespace pg_default;

  create table
  public.transactions (
    id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    description text null,
    time_id bigint null,
    constraint order_transaction_pkey primary key (id),
    constraint gold_transactions_time_id_fkey foreign key (time_id) references "time" (id)
  ) tablespace pg_default;