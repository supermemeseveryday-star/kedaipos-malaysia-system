# Kedai POS

An open-source, local-first point-of-sale and order-taking system for Malaysian small retailers. One shop runs the service on its main computer; staff use a browser on that computer, an iPad, or a phone over the shop's Wi-Fi/LAN.

The first release uses Python's standard library and SQLite. It has no Python package dependencies and needs no internet connection for local checkout.

## Features

- Owner setup and owner-managed staff accounts
- Responsive cashier and employee order-taking interface
- Product catalog with custom categories, SKU/barcode field, photos, prices, and stock
- Shared orders, cash checkout, manually confirmed DuitNow QR, cash change, receipt numbers, and printer-friendly receipts
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

No third-party runtime dependencies are currently required. Source is in `server.py` and `static/`. See `docs/plans/` for the approved product design and implementation plan.

## Publish to GitHub

See [`docs/github-publishing.md`](docs/github-publishing.md) for steps to publish this local repository. Keep the shop's `data/` directory and OAuth credentials out of the public repository.
