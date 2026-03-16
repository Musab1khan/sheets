import frappe
from cron_descriptor import get_description

CRON_MAP = {
    "Yearly": "0 0 1 1 *",
    "Monthly": "0 0 1 * *",
    "Weekly": "0 0 * * 0",
    "Daily": "0 0 * * *",
    "Hourly": "0 * * * *",
}


@frappe.whitelist(methods=["GET"])
def get_all_frequency():
    return (frappe.conf.scheduler_interval or 240) // 60


@frappe.whitelist(methods=["GET"])
def describe_cron(cron: str):
    if cron in CRON_MAP:
        cron = CRON_MAP[cron]
    return get_description(cron)


@frappe.whitelist()
def export_customers_to_sheets(doc=None, method=None, sheet_url=None):
    import gspread
    from google.oauth2.service_account import Credentials
    
    # 1. Get credentials from SpreadSheet Settings
    creds_file = frappe.get_all('File', filters={
        'attached_to_doctype': 'SpreadSheet Settings',
        'attached_to_name': 'SpreadSheet Settings'
    }, fields=['file_url'])
    
    if not creds_file:
        frappe.throw("Google Sheets Credentials not found in SpreadSheet Settings")
        
    creds_path = frappe.get_site_path() + creds_file[0].file_url
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(creds)
    
    # 2. Use provided URL or find from SpreadSheet doctype
    if not sheet_url:
        sheet_doc = frappe.get_all('SpreadSheet', filters={'sheet_name': 'Customer'}, fields=['sheet_url'], limit=1)
        if sheet_doc:
            sheet_url = sheet_doc[0].sheet_url
        else:
            frappe.throw("No SpreadSheet document found for 'Customer'")
            
    # 3. Open Sheet
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.get_worksheet(0)
    

    # 4. Get Customer Data with Child Table
    customers = frappe.get_all("Customer", fields=["name", "customer_name", "customer_group", "territory", "mobile_no", "email_id"])
    
    header = ["ID", "Customer Name", "Customer Group", "Territory", "Mobile", "Email", "Item Code", "Item Name", "Total Orders", "Total Qty", "UOM", "Last Order Date"]
    data = [header]
    
    for c in customers:
        doc = frappe.get_doc("Customer", c.name)
        
        # If there are bonded products, create a row for each
        if doc.custom_bonded_products:
            for p in doc.custom_bonded_products:
                data.append([
                    doc.name,
                    doc.customer_name,
                    doc.customer_group,
                    doc.territory,
                    doc.mobile_no,
                    doc.email_id,
                    p.item_code,
                    p.item_name,
                    p.total_orders,
                    p.total_ordered_qty,
                    p.uom,
                    str(p.last_order_date) if p.last_order_date else ""
                ])
        else:
            # If no bonded products, just add the customer info
            data.append([
                doc.name,
                doc.customer_name,
                doc.customer_group,
                doc.territory,
                doc.mobile_no,
                doc.email_id,
                "", "", "", "", "", ""
            ])
    
    # 5. Push to Sheet
    worksheet.clear()
    worksheet.update('A1', data)
    
    return f"Successfully synced {len(customers)} customers and their bonded products."
