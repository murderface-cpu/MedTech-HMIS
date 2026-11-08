# User access

## Modules

Access is granted per module. Each module is a Django group created by migration
`manager.0003_seed_groups_and_titles`:

Patients, Doctor, Laboratory, Cardiology, Radiology, Pharmacy, Inventory, Theatre, Dental, Finance,
Administration.

A user sees in the navigation, and can open, only the modules whose groups they belong to.
Superusers have every module.

## Create the first administrator

```bash
python manage.py createsuperuser
```

## Add a staff member

1. Sign in as a user with the Administration module and open **Admin** (`/admin/`).
2. Under **Staff**, fill in the person's details and title.
3. In **Sign-in account**, enter a username and an initial password, and tick the modules the
   person needs. Leave the username empty for staff who do not use the system.
4. Save. A staff member whose title is a doctor title is also registered as a doctor and appears
   in doctor selections.

To change modules later, open the staff member from the staff list and edit **Sign-in account**.
Leave the password empty to keep the current one.

## Suspend access

Open the staff member and untick **Account can sign in**. The account becomes inactive: it can no
longer sign in, its existing sessions stop being accepted, and its records remain.

## Passwords

Users change their own password at `/password/`. An administrator sets a new password in the
staff member's **Sign-in account** section. Never send passwords by email or chat.
