"""Compare pre-install native records after addon installation or update."""
import json


assert env["ir.module.module"].search([("name", "=", "pos_revolut")]).state == "installed"
snapshot = json.loads(env["ir.config_parameter"].sudo().get_param(
    "pos_revolut_test.native_install",
))
for entry in snapshot:
    records = env[entry["model"]].browse(entry["ids"]).exists()
    assert records.ids == entry["ids"], f"Native {entry['model']} records were removed"
    observed = json.loads(json.dumps(records.read(entry["fields"], load=False), default=str, sort_keys=True))
    # Many2many relations are sets; database row order is not business data.
    for name in entry["fields"]:
        if records._fields[name].type == "many2many":
            for values in observed + entry["values"]:
                values[name] = sorted(values[name])
    assert observed == entry["values"], f"Native {entry['model']} history changed: {observed!r}"
print("Preserved all pre-install native customer, product, register, sale and accounting values")
