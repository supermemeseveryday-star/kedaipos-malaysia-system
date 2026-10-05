Kedai POS

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
