"""
Vendored DOL Form 5500 record layouts, one JSON document per form year.

Each document mirrors the ``*_layout.txt`` files published alongside the
datasets on the EBSA public-disclosure page::

    {
      "form_year": 2023,
      "source": "https://askebsa.dol.gov/FOIA%20Files/2023/Latest/",
      "datasets": {
        "F_5500": [{"p": 1, "n": "ACK_ID", "t": "TEXT", "s": 30}, ...],
        ...
      }
    }

Regenerate with ``python -m scripts.refresh_layouts``. Do not edit by hand.
"""
