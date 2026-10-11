# Kedai POS

An open-source, local-first point-of-sale and order-taking system for Malaysian small retailers. One shop runs the service on its main computer; staff use a browser on that computer, an iPad, or a phone over the shop's Wi-Fi/LAN.

The first release uses Python's standard library and SQLite. It has no Python package dependencies and needs no internet connection for local checkout.

## Features

- Owner setup and owner-managed staff accounts
- Responsive cashier and employee order-taking interface
- Product catalog with custom categories, SKU/barcode field, photos, prices, and stock
- Shared orders, cash checkout, manually confirmed DuitNow QR, cash change, receipt numbers, and printer-friendly receipts
- Scan-to-order: per-table QR codes; customers order and pay online without logging in (Malaysian e-wallets, Apple Pay, Google Pay, cards, FPX through a payment gateway)
- Full and partial refunds (online refunds go back through the gateway) and a live daily settlement with day closing and CSV export
- Stock deduction on settlement and protection against settling an order twice
- Expense ledger, daily sales summary, tax setting, and downloadable data backup
- Bahasa Melayu, English, and Simplified Chinese interface
- Optional owner-only Google OAuth and Google Sheets sync for products, sales, and expenses
- Local server remains usable when external internet is unavailable, provided the host computer and shop LAN are available

## Start on Windows

1. Install Python 3.11 or newer.
2. Extract or clone this folder onto the shop's main computer.
3. Double-click `run.bat` or run `python server.py` in PowerShell from this folder.
4. On the main computer, open [http://localhost:8765](http://localhost:8765) and create the owner account.
5. Find the main computer's private LAN IPv4 address with `ipconfig`.
6. Connect the iPad/phone to the same shop Wi-Fi and open `http://<LAN-IP>:8765` (for example `http://192.168.1.25:8765`).
7. If Windows Firewall asks, allow Python on **Private networks only**. A DHCP reservation for the host makes its address stable.

On macOS/Linux, run `./run.sh` or `python3 server.py`.

## First shop setup

- Add products and stock from **Products**. Product images are resized in the browser before upload.
- Upload the shop's merchant DuitNow QR image in **Settings**. The app displays it at checkout; staff must confirm payment themselves.
- Add employee usernames and passwords from **Settings**. Employees can create orders and take payment. Shop settings, staff, product editing, reports, expenses, and Google connection are owner-only.
- If the shop is SST-registered, configure the applicable tax label/rate with the business's accountant. The setting is not a determination that a tax applies.
- The host uses `Asia/Kuala_Lumpur` timestamps by default. Set `KEDAI_TIMEZONE` only if operating in another timezone.

## Google Sheets (optional)

Google connection must be started in a browser on the **main computer** at `http://localhost:8765`. The server rejects OAuth starts from employee tablets or phones; those devices can still use POS and orders on the LAN.

1. In Google Cloud Console, create a project and enable the Google Sheets API.
2. Configure the OAuth consent screen and add the shop owner's Google account as a test user while the application is in testing.
3. Create an OAuth client of type **Web application**. Add this exact authorized redirect URI: `http://localhost:8765/api/google/callback` (or replace `8765` with the configured `KEDAI_PORT`).
4. In Kedai POS **Settings**, enter the OAuth Client ID and Client Secret, enable sync, and save. The app creates a dedicated `Products`, `Sales`, and `Expenses` spreadsheet on first sync.
5. Choose whether the owner permits product/stock and/or expense edits made in Sheets to be imported back. POS wins conflicts; settled receipt/payment facts are always exported from POS.
6. Select **Connect Google**, approve access, then select **Sync now**. Automatic sync retries while the host has internet access.

The integration uses Google's `drive.file` scope and the Google account's email scope. It stores the refresh token in the shop's local SQLite database; protect the host computer and backup files. Google OAuth setup and verification requirements depend on how the open-source project is distributed.

## Scan-to-order and online payments

### How it works

1. Each table has a QR code pointing to `/order?table=<code>`. The code is random, so tables can't be guessed.
2. The customer picks dishes and a payment method. The server prices the cart from the database (prices sent by the phone are ignored) and creates a *checkout session* and a pending *payment*. It then sends the customer to the gateway's payment page.
3. The gateway reports the result with a **signed webhook** to `/api/payments/webhook/<provider>`. The server:
   - verifies the signature and the amount, then creates the order as `paid`, deducts stock and assigns the receipt number, all in one transaction;
   - ignores repeated webhooks, so a retried webhook never creates a second order;
   - if an item sold out while the customer was paying, refunds the payment automatically instead of creating an order.
4. The order shows up in the POS with its table and a sound alert. The customer's phone shows the receipt.

Unpaid checkouts never appear in the POS. Data lives in the `dining_tables`, `checkout_sessions`, `payments`, `refunds` and `day_closings` tables. The code is in `ordering.py`.

### Making it reachable from customers' phones

Customers on mobile data cannot reach a computer on the shop LAN. The recommended setup keeps the POS on the shop computer and publishes it through **Cloudflare Tunnel** (free, no router or firewall changes):

```bash
# one-off test URL (changes every time it starts)
cloudflared tunnel --url http://localhost:8765
# for daily use, create a named tunnel with your own domain, e.g. order.your-shop.com:
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
```

Enter the resulting `https://` address in **Settings → Scan-to-order → Public address**, then print the table QR codes.

**Security model.** Any request that arrives through the tunnel or another reverse proxy can only reach the customer pages, the public API, the payment webhook and product images. That means any request with a `Cf-Connecting-Ip` or `X-Forwarded-For` header, or one whose `Host` matches the public address. The cashier screen, login, settings, backups and every staff or owner API return `404` from the internet. Checkouts are rate-limited per device.

### Payment gateway

Taking Malaysian e-wallets, Apple Pay and Google Pay requires a merchant account with a payment gateway. Fiuu (formerly Razer Merchant Services), Stripe, iPay88 and Billplz are common choices. The application is made by the business, usually with its SSM registration.

This release ships **`MockGateway`**, a simulated hosted checkout that exercises the whole flow, including signed webhooks and refunds, without moving money. The customer page, the payment page and the POS settings all show a *test mode* warning while it is active.

To connect a real provider, add a class in `ordering.py` with the same three methods and return it from `gateway()`:

| Method | Responsibility |
|---|---|
| `create(session) -> {provider_ref, redirect_url}` | Create the payment with the provider and return where to send the customer |
| `verify_webhook(headers, raw_body) -> {provider_ref, status, amount_cents}` | Check the provider's signature and normalise its event (`succeeded` / `failed`) |
| `refund(payment, amount_cents) -> provider_refund_ref` | Refund all or part of a captured payment |

Point the provider's webhook/callback URL at `https://<public address>/api/payments/webhook/<provider>`. Keep the provider's secret keys out of the repository. Read them from environment variables on the shop computer.

### Refunds and settlement rules

- **Refunds:** owners refund paid orders fully or partially.
  - Online payments are refunded through the gateway.
  - Cash and DuitNow refunds are recorded after the money is handed back.
  - A full refund can restock the items; partial refunds never restock.
  - A refund is recorded on the day it is made. Its order keeps its original sale date.
- **Settlement** (`/api/settlement?day=YYYY-MM-DD`):
  - Gross sales are paid orders by payment date; refunds are counted by refund date; net = gross − refunds.
  - Breakdowns by method, tax, expenses and expected cash in the drawer (cash sales − cash refunds).
  - **Close the day** stores a snapshot with the counted cash and the variance.
  - `/api/settlement/export` downloads a CSV that opens in Excel, for the accountant.

## Data, backup, and restore

- Local data: `data/kedai.sqlite3`; uploaded product/QR images: `data/images/`.
- An owner can download a ZIP backup from **Reports** or **Settings**. The archive includes the database and uploaded images. It contains sensitive shop records; store it securely.
- To restore, stop Kedai POS, extract the archive into a safe temporary folder, then replace `data/kedai.sqlite3` and the contents of `data/images/`; restart the server.
- Backups are not uploaded automatically. Keep a separate copy on encrypted storage.

## Configuration

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `KEDAI_HOST` | `0.0.0.0` | Interface to bind; keep the host on a trusted private network |
| `KEDAI_PORT` | `8765` | HTTP port; update the OAuth callback URI if changed |
| `KEDAI_DATA_DIR` | `./data` | Database and image storage directory |
| `KEDAI_TIMEZONE` | `Asia/Kuala_Lumpur` | Business timestamp timezone |

## Connectivity model

Shop devices use the host computer over the shop LAN. This path does not depend on the internet and carries shared orders while external internet is down. Internet is used for Google authorization and Sheets sync. The host computer must stay on and connected to the router. Bluetooth is not used for order sync; browser Bluetooth support is not consistent on iPad.

## Legal and operational notes

This is an initial open-source release, not certified accounting, SST, or MyInvois software. Tax and e-Invoice obligations depend on the merchant and current rules. Review current official resources before relying on tax calculations or receipts:

- [LHDN e-Invoice](https://www.hasil.gov.my/e-invois/)
- [Royal Malaysian Customs MySST Orders](https://mysst.customs.gov.my/sst-orders/)
- [Personal Data Protection Commissioner](https://www.pdp.gov.my/ppdpv1/en/akta/pdp-act-2010-en/)

## Development

No third-party runtime dependencies are currently required. Source is in `server.py` and `static/`.

Run the API tests (they use a temporary data folder and never touch `data/`):

```
python -m unittest discover -s tests
```

## Publishing

The repository's `.gitignore` excludes `data/`, SQLite files, and backup ZIPs. Keep the shop's `data/` directory, backups, and Google OAuth credentials out of any public repository.
