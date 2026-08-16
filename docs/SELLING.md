# Selling 401K Finder Pro

How to put the installer online, take payment, and issue a licence that is tied
to one customer's machines.

The application already has the client half built: activation, machine binding,
an offline grace period and the management commands. What remains is choosing a
store, configuring three values, and the paperwork.

> **Verify before you commit.** Vendor pricing, features and ownership in this
> space change frequently — Lemon Squeezy was acquired by Stripe, for instance.
> Treat every fee and feature below as a starting point to check, not as
> current fact.

---

## Contents

1. [Start here: what you are actually selling](#1-start-here-what-you-are-actually-selling)
2. [Choosing a store](#2-choosing-a-store)
3. [Setting up Lemon Squeezy](#3-setting-up-lemon-squeezy)
4. [Configuring the application](#4-configuring-the-application)
5. [Hosting the installer](#5-hosting-the-installer)
6. [How the licensing works](#6-how-the-licensing-works)
7. [What this does not prevent](#7-what-this-does-not-prevent)
8. [Legal requirements](#8-legal-requirements)
9. [Supporting customers](#9-supporting-customers)
10. [Testing the whole flow](#10-testing-the-whole-flow)

---

## 1. Start here: what you are actually selling

Be precise about this, because it shapes your marketing and protects you.

**The Form 5500 data is public domain.** Anyone can download the same files from
the Department of Labor for free. You have no exclusive rights to it and cannot
acquire any.

**What you are selling is the tool**: the 448 vendored record layouts, the
two-pass join that makes schedules resolve to plans, provider extraction across
five schedules, the plan classifier, the evidence trail, and the fact that all
of it runs on a laptop instead of requiring a data engineer.

That is a genuine product and worth money. But your copy must never imply
exclusive access to the data, or that the data itself is yours. "Search DOL
Form 5500 filings" is accurate. "Our proprietary retirement plan database" is
not, and invites a complaint you do not need.

---

## 2. Choosing a store

The decision that matters is not the checkout page. It is **who is the legal
seller of record**, because that determines who owes sales tax.

### Merchant of Record

The platform sells to your customer; you sell to the platform. They register
for, collect and remit VAT and sales tax in every jurisdiction.

| | |
|---|---|
| **Examples** | Paddle, FastSpring, Lemon Squeezy, Gumroad |
| **Fees** | Roughly 5% + a fixed amount per transaction |
| **You handle** | Making the software |
| **They handle** | Payment, tax registration, filing, invoices, refunds, fraud |

### Payment processor

| | |
|---|---|
| **Examples** | Stripe, PayPal |
| **Fees** | Roughly 2.9% + 30¢ |
| **You handle** | Tax registration and filing in every jurisdiction you sell into |

### The recommendation

**Use a merchant of record.** The EU charges VAT on digital goods from the first
sale with no threshold, and roughly a hundred jurisdictions have their own
rules. The extra ~2% buys you out of a compliance problem that will otherwise
consume more of your time than the software does.

Of those, **Lemon Squeezy** is the default this guide assumes, because its
licence API does exactly what "cannot be shared" requires: it issues keys and
counts machine activations against a limit you set. Gumroad's API counts uses
but cannot release a seat, so a customer changing laptops needs you to intervene
by hand.

---

## 3. Setting up Lemon Squeezy

1. **Create a store** and complete the payout details.
2. **Create a product** — "401K Finder Pro", one-time payment, your price.
3. **Enable licence keys** on the product. Set:
   - **Activation limit: 2** — enough for a desktop and a laptop. One is
     technically stricter but generates constant support mail from people who
     bought a new machine.
   - **Expiry: never**, for a one-time purchase.
4. **Upload the installer** as the deliverable, or point the delivery at your own
   signed URL (see below).
5. Note the **product ID** — you need it in the next step.

Customers receive their key by email on purchase. The application asks for it
on first launch.

---

## 4. Configuring the application

Open [`app/licensing/config.py`](../app/licensing/config.py) and edit the block
marked *"Edit this before a release build"*:

```python
LICENSE_CONFIG = LicenseConfig(
    provider=Provider.LEMON_SQUEEZY,
    product_id="123456",                          # from your store
    purchase_url="https://yourstore.lemonsqueezy.com/checkout/...",
    account_url="https://app.lemonsqueezy.com/my-orders",
    support_email="support@yourdomain.com",
)
```

Then rebuild:

```powershell
.\build.ps1 -Clean -Installer
```

**Until you set a provider, licensing is off and the application runs
unlicensed.** That is the right default for development and for anyone building
from source, but it means a release built without this step gives itself away.
Check before you publish:

```powershell
401k-finder.exe license status
```

A build ready to sell says *"Not activated"*. One that is not says *"This build
has no licence server configured"*.

### Testing without rebuilding

Environment variables override the compiled configuration, but **only when the
compiled configuration has licensing switched off** — so a released build cannot
have its licensing disabled by setting a variable:

```powershell
$env:FINDER_401K_LICENSE_PROVIDER = "lemonsqueezy"
$env:FINDER_401K_LICENSE_PRODUCT  = "123456"
python -m app.cli license activate YOUR-TEST-KEY
```

---

## 5. Hosting the installer

The installer is around 200 MB, so this is a real bandwidth cost at volume.

**Do not put it behind a plain public link.** Anyone who finds the URL skips
your checkout entirely. Serve it through **expiring signed URLs** issued after
purchase — most stores do this for you if you upload the file as the
deliverable.

If you host it yourself:

| Option | Why |
|---|---|
| **Cloudflare R2** | No egress fees. At 200 MB per download that dominates everything else. |
| **Backblaze B2** | Cheap, free egress via Cloudflare. |
| **AWS S3** | Works, but egress is billed per gigabyte and adds up quickly. |

Publish a SHA-256 checksum beside the download so buyers can verify it:

```powershell
Get-FileHash "dist\installer\401KFinderPro-Setup-2.0.0.exe" -Algorithm SHA256
```

**Code signing is no longer optional once you charge.** A paid product that
opens with *"Windows protected your PC"* will bleed refunds. See
[`WINDOWS_APPLICATION.md`](WINDOWS_APPLICATION.md) for the signing steps.

---

## 6. How the licensing works

```
purchase          store issues a licence key, emails it to the buyer
first launch      application shows the activation dialog
activation        POST {key, machine fingerprint} to the store
                  store checks: valid key? under the activation limit?
                  yes -> records this machine, returns an instance id
                  no  -> refused, with the reason
stored locally    %LOCALAPPDATA%\401K Finder Pro\license.json
                  signed with a key derived from the machine fingerprint
every launch      record is fresh (under 7 days) -> start, no network call
                  record is stale -> re-confirm with the store
```

### The machine fingerprint

Derived from the Windows `MachineGuid` and the system volume serial, then
hashed. **The store only ever sees the hash**, never a hardware serial — which
keeps a licence check from becoming hardware inventory collection, and keeps
your privacy policy short and honest.

Customers can see their own with `401k-finder.exe license status`, which is the
first thing to ask for when someone reports an activation problem.

### Deliberate choices that will save you support mail

| Behaviour | Why |
|---|---|
| **30-day offline grace period** | If your store has an outage, or the customer is on a plane or behind a corporate proxy, the application keeps working. Locking out someone who paid because *your* infrastructure is unreachable is the worst possible failure. |
| **Re-checks only every 7 days** | Ordinary launches cost nothing and work offline. |
| **Refusal to activate is reported as a network problem when it is one** | Blaming the key for your outage sends confused customers to support. |
| **Self-service deactivation** | `license deactivate` frees the seat so people can move machines without emailing you. |
| **Two activations by default** | One is stricter and generates constant mail from people who replaced a laptop. |

### The commands

```powershell
401k-finder.exe license status              # what is active, and this machine's ID
401k-finder.exe license status --check      # force a re-check with the store
401k-finder.exe license activate KEY        # activate
401k-finder.exe license deactivate          # release this machine
```

---

## 7. What this does not prevent

Say this to yourself once, clearly: **you cannot make this uncrackable, and any
vendor who claims otherwise is selling obfuscation theatre.**

The application runs on hardware the customer controls. They can attach a
debugger, patch the binary, or block the licence server in their hosts file.
**A PyInstaller build is softer than most** — the Python bytecode sits in the
archive and can be extracted and decompiled, so someone competent can find and
remove the check in an afternoon.

What this system actually achieves:

- Handing a key to a colleague **fails** once the activation limit is reached.
- Copying `license.json` to another machine **fails** — the signature is bound
  to the fingerprint.
- Refunds and chargebacks **end access** at the next re-check.
- A casual user has no route to sharing that works.

That is the realistic goal, and it is what commercial desktop software actually
delivers. The people who would crack it were never going to pay; the people who
would pay are not going to crack it. Spend your effort on the product.

If you later want stronger protection, the meaningful step is not more
obfuscation — it is **moving something valuable server-side**, so a cracked
client is missing a capability rather than just a check.

---

## 8. Legal requirements

Not optional, and cheap to get right at the start.

### You need three documents

1. **EULA / licence terms** — what the customer may do with the software, how
   many machines, no warranty, limitation of liability.
2. **Privacy policy** — you collect an email address (via the store) and a
   hashed machine identifier. Both must be disclosed, with a retention period
   and a contact for deletion requests. The hashed fingerprint is still personal
   data under GDPR.
3. **Refund policy** — a merchant of record will require one. EU consumers have
   a 14-day right of withdrawal for digital goods unless they explicitly waive
   it at purchase, which the store's checkout normally handles.

### Say what the tool is not

Add this to your terms and your site, because someone will otherwise assume
otherwise:

> 401K Finder Pro reports what public Form 5500 filings say. It is not
> financial, legal, tax or investment advice, and it does not evaluate fees,
> fiduciary conduct or plan health.

### One more

If you sell into the EU or UK you are processing personal data as a controller.
That means a lawful basis, a retention period, and honouring deletion requests.
Keeping the licensing data minimal — an email and a hash — makes this
straightforward, which is exactly why the fingerprint is hashed.

---

## 9. Supporting customers

Four situations account for nearly all licence mail.

**"My key does not work."** Ask for the output of
`401k-finder.exe license status`. It shows the machine ID and the last
confirmation, which is usually enough to see the problem.

**"I have used all my activations."** Look up the key in your store and release
the stale instance. This is the common case for someone who replaced a machine
without deactivating first — which is why the limit is 2 rather than 1.

**"It says my licence is not valid."** Check for a refund or chargeback on the
order. If neither, the store may have been unreachable past the grace period —
have them run `license status --check` while online.

**"I reinstalled Windows and now it will not activate."** A Windows reinstall
changes `MachineGuid`, so it looks like a new machine. Release the old seat.

Consider a short **support page** covering these four, and link it from the
activation dialog's support address. Most customers will solve their own problem
if you let them.

---

## 10. Testing the whole flow

Before announcing anything, buy your own product on a clean machine.

1. **Configure and build** with your real product ID.
2. **Confirm licensing is on**: `401k-finder.exe license status` should say
   *"Not activated"*.
3. **Buy it yourself**, with a real card, through the real checkout. Use the
   store's test mode first, then do it live once — the live path is the one
   your customers take.
4. **Check the email** arrives, reads clearly, and contains the key.
5. **Activate** on a clean VM with no Python installed.
6. **Verify the seat limit**: activate on a second machine (should work), then a
   third (should be refused with a clear message).
7. **Verify deactivation** frees the seat.
8. **Verify offline use**: disconnect and confirm the application still starts.
9. **Refund yourself**, then run `license status --check` and confirm access
   ends.
10. **Confirm the data still works** — download a form year and run a search.
    Licensing must not have broken the actual product.

Step 9 is the one people skip, and it is the one that determines whether a
chargeback costs you a sale or costs you a customer who keeps using the
software for free.
