# A recipe created without a status gets the first in sort order

The oldest among equals; with no status at all the create is a 422 saying so.
There is no server default because the first status is the owner's data: a
column default would name an id that 未來固定設定 can reorder or delete.

Rejected:

- **Making the status optional**, which leaves every list and the status
  toggle a "none" case for a recipe that has simply not been touched.
- **A fixed "first status" flag**, a second ordering beside `sort_order` for
  the owner to keep in step.
