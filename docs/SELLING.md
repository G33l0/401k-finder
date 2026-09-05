# Selling 401K Finder Pro

How to put the installer online, take payment your own way, and issue a licence
key that only works on the buyer's computer.

There is no store integration, no payment provider and no licence server. A
buyer emails you, you agree a price and a payment method between you, and you
reply with a key. The application checks that key entirely on the customer's
machine.

That is a deliberate trade. You give up automated checkout; you get no monthly
fees, no platform that can suspend your account, no server to keep running, and
nothing that can be down when a customer is trying to work. It suits a product
sold in small numbers at a considered price. It does not suit volume.

---

## Contents

1. [What you are actually selling](#1-what-you-are-actually-selling)
2. [How the licensing works](#2-how-the-licensing-works)
3. [One-time setup: your signing key](#3-one-time-setup-your-signing-key)
4. [Hosting the installer](#4-hosting-the-installer)
5. [Selling one: the whole flow](#5-selling-one-the-whole-flow)
6. [Taking payment](#6-taking-payment)
7. [What this does not prevent](#7-what-this-does-not-prevent)
8. [Legal requirements](#8-legal-requirements)
9. [Supporting customers](#9-supporting-customers)
10. [Testing the whole flow](#10-testing-the-whole-flow)

---

## 1. What you are actually selling

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

### The one claim that will get you in trouble

The **Find my accounts** feature traces a person's work history to the plans
their employers ran. It is the most saleable thing in the product, and it is
also the easiest to describe dishonestly.

**Never advertise that it finds an account by Social Security number.** It does
not, and no tool built on this data can: Form 5500 is what an employer files
about a *plan*, and across all 448 published record layouts there is no
participant name, no SSN and no individual balance. A page saying "enter your
SSN to find your lost 401(k)" would be describing a capability the software
does not have, over a product that charges money, in a category regulators
watch closely, and it is indistinguishable from the scams that operate in this
exact space.

| Say this | Not this |
|---|---|
| "Find which retirement plan your old employer ran, and who holds the money" | "Find your lost 401(k) by SSN" |
| "Identifies the plan, its EIN, and the recordkeeper to contact" | "Locates your account balance" |
| "Built from public Department of Labor filings" | "Searches a nationwide database of retirement accounts" |

The application enforces this from the inside. An SSN typed into the employer
box is refused, never stored, and the user is pointed at the Department of
Labor's Retirement Savings Lost and Found, which does take one. Keep your
marketing on the same side of that line.

---

## 2. How the licensing works

```
buyer opens the app     it shows a Machine ID and your email address
buyer emails you        with that Machine ID
you agree a price       however you like. The software is not involved
you issue a key         signed with your private key, for that Machine ID
buyer pastes the key    checked on the spot, offline, and stored
every launch after      re-checked against the same machine. No network.
```

A key is a small signed record: the machine it was issued for, an optional
expiry, and the customer's name, all covered by an **Ed25519 signature**.

The application carries only the **public** half of your signing key. That is
what makes this safe to ship: the public key verifies licences and cannot
create them. Someone who unpacks the executable finds nothing they can use to
issue a key.

### Why it is bound to a machine

The Machine ID is derived from the Windows `MachineGuid` and the system volume
serial, then hashed. **It never leaves the customer's computer except when they
choose to email it to you**, and it is a hash, not a hardware serial, so this
is not hardware inventory collection and your privacy policy stays short.

Because the key names one machine, handing it to a colleague does nothing. So
does copying `license.json` between computers: the key inside it still names the
first machine.

### Expiring keys

Keys are perpetual by default. Pass `--days 365` to issue an annual licence, and
the application refuses to start the day after it lapses. Use this if you want
to sell subscriptions. It is the only leverage you have, because **there is no
revocation**. See section 7.

---

## 3. One-time setup: your signing key

Do this once, before your first release.

```powershell
python -m scripts.issue_license --new-keypair
```

It writes a private key to `%USERPROFILE%\.401k-finder\signing-key.hex` and
prints the matching public key.

Paste the public key into
[`app/licensing/config.py`](../app/licensing/config.py):

```python
LICENSE_CONFIG = LicenseConfig(
    public_key="d4646994930056ecfc3e18bf29cca4a01830e66e963b9064c4ecdcda6563bec0",
    support_email="aliennyx@aol.com",
)
```

Then rebuild:

```powershell
.\build.ps1 -Clean -Installer
```

> ### The signing key is the business
>
> Anyone holding it can issue licences for your product, for free, forever.
>
> - **Back it up.** Lose it and every future key needs a new keypair, which
>   means a new build and a new key for every existing customer.
> - **Never commit it.** It is stored outside the repository on purpose.
> - **Keep it off the build machine** if you can. Issue keys from a laptop, or
>   pass it through `$env:FINDER_401K_LICENSE_SEED` from a password manager.

**Until you set a public key, licensing is off and the application runs
unlicensed.** That is the right default for development and for anyone building
from source, but it means a release built without this step gives itself away.
`build.ps1` warns you, and you can check directly:

```powershell
401k-finder.exe license status
```

A build ready to sell says *"Not activated"*. One that is not says *"This build
has no licence key configured"*.

### Testing without rebuilding

An environment variable overrides the compiled configuration, but **only when
the compiled configuration has licensing switched off**, so a released build
cannot have its licensing disabled by setting a variable:

```powershell
$env:FINDER_401K_LICENSE_PUBKEY = "d46469949300..."
python -m app.cli license status
```

---

## 4. Hosting the installer

The installer is around 200 MB, so this is a real bandwidth cost at volume.

Because payment happens by email, you have a choice the automated route does
not give you: **send the download link only to people who have paid.** A plain
public link is fine if you would rather let anyone download it and gate on the
licence instead. An unlicensed copy will not start.

If you host it yourself:

| Option | Why |
|---|---|
| **Cloudflare R2** | No egress fees. At 200 MB per download that dominates everything else. |
| **Backblaze B2** | Cheap, free egress via Cloudflare. |
| **AWS S3** | Works, but egress is billed per gigabyte and adds up quickly. |

Publish a SHA-256 checksum beside the download so buyers can verify it:

```powershell
Get-FileHash "dist\installer\401KFinderPro-Setup-2.1.0.exe" -Algorithm SHA256
```

**Code signing is no longer optional once you charge.** A paid product that
opens with *"Windows protected your PC"* will bleed refunds. See
[`WINDOWS_APPLICATION.md`](WINDOWS_APPLICATION.md) for the signing steps.

---

## 5. Selling one: the whole flow

**1. They install and open it.** The activation window shows their Machine ID,
your email address, and an *"Email us for a licence…"* button that opens a
message with the Machine ID already in it.

**2. They email you.** You will get something like:

> 401K Finder Pro 2.1.0
> Machine ID: 2580db0d3f7e83ff3759d14a76731aa2

**3. You agree a price and take payment.** See the next section.

**4. You issue the key:**

```powershell
python -m scripts.issue_license `
    --machine 2580db0d3f7e83ff3759d14a76731aa2 `
    --label "Acme Corp" `
    --email
```

`--email` prints a complete reply, covering the key, activation instructions and the terms,
ready to paste into your mail client. Without it you get just the key.

Add `--days 365` for an annual licence, or `--expires 2027-03-31` for a fixed
date.

**5. They paste it in and click Activate.** Done: offline, instantly, and it
keeps working with no further contact.

### Moving a customer to a new computer

They send the new Machine ID; you issue a new key. There is no seat to release
and nothing to revoke, so decide your own policy. Most people simply reissue.
If that worries you, sell annual keys, which bound how long a duplicate is
useful.

---

## 6. Taking payment

The software is not involved, so use whatever you and the buyer agree. Common
choices, with the thing that actually matters about each:

| Method | Watch out for |
|---|---|
| **Bank transfer / invoice** | Best for business buyers, who often prefer it. No fees. Slow to clear. |
| **PayPal invoice** | Fast and familiar. Buyer-friendly chargeback rules, and you cannot revoke a key after a reversal. |
| **Stripe payment link** | A link you paste into an email. Around 2.9% + 30¢. You handle your own tax. |
| **Wise / Revolut** | Good for cross-border, low FX cost. |

**You are the seller of record.** Nobody is collecting VAT or sales tax for you.
If you sell to consumers in the EU or UK, VAT on digital goods is due from the
first sale with no threshold. Selling business-to-business inside the EU usually
shifts that to the buyer under the reverse charge, but you need their VAT
number on the invoice.

**Take payment before you issue the key.** You cannot take it back afterwards.

---

## 7. What this does not prevent

Say this to yourself once, clearly: **you cannot make this uncrackable, and any
vendor who claims otherwise is selling obfuscation theatre.**

The application runs on hardware the customer controls. They can attach a
debugger, patch the binary, or replace the public key with their own. **A
PyInstaller build is softer than most.** The Python bytecode sits in the
archive and can be extracted and decompiled, so someone competent can find and
remove the check in an afternoon.

Be clear about the one real gap in this design:

> **There is no revocation.** A key, once issued, works on that machine forever
> (or until its expiry date). If someone pays and reverses the payment, you
> cannot switch them off. Your only real controls are taking payment first, and
> issuing keys that expire.

What this system does achieve:

- Handing a key to a colleague **fails**, because it names one machine.
- Copying `license.json` to another machine **fails**, for the same reason.
- Nobody can build a key generator from the shipped application, because it
  holds no secret capable of signing.
- A casual user has no route to sharing that works.

That is what commercial desktop software actually delivers. The people who would
crack it were never going to pay; the people who would pay are not going to
crack it. Spend your effort on the product.

If you later want stronger protection, the meaningful step is not more
obfuscation. It is **moving something valuable server-side**, so a cracked
client is missing a capability rather than just a check.

---

## 8. Legal requirements

Not optional, and cheap to get right at the start.

### You need three documents

1. **EULA / licence terms.** What the customer may do with the software, how
   many machines, no warranty, limitation of liability.
2. **Privacy policy.** You receive an email address and a hashed machine
   identifier. Both must be disclosed, with a retention period and a contact for
   deletion requests. The hashed Machine ID is still personal data under GDPR.
3. **Refund policy.** State it plainly. EU consumers have a 14-day right of
   withdrawal for digital goods unless they explicitly waive it, and since you
   are selling directly, getting that waiver in writing before you send the key
   is on you.

Selling by email means every one of these has to be linked from your site or
quoted in your reply, because there is no checkout page to carry them.

### Say what the tool is not

Add this to your terms and your site, because someone will otherwise assume
otherwise:

> 401K Finder Pro reports what public Form 5500 filings say. It is not
> financial, legal, tax or investment advice, and it does not evaluate fees,
> fiduciary conduct or plan health.

### Keep a record of what you issued

The application keeps none. Keep your own list of Machine ID, customer, date,
expiry and what they paid, or you will not be able to answer "did this person
buy?" when they email you in two years. A spreadsheet is enough.

---

## 9. Supporting customers

Four situations account for nearly all licence mail.

**"My key does not work."** Ask for the output of
`401k-finder.exe license status`. If it says *"issued for a different
computer"*, the Machine ID changed, so reissue. If it says *"not valid"*, the key
was truncated in copying; send it again.

**"I have a new computer."** They send the new Machine ID; you issue a new key.

**"I reinstalled Windows and now it will not activate."** A Windows reinstall
changes `MachineGuid`, so it looks like a new machine. Reissue.

**"Nothing happens when I click Email us."** They have no mail client
configured. The application copies the address and Machine ID to the clipboard
and says so, so they can write from webmail.

Consider a short **support page** covering these four, and link it from your
site. Most customers will solve their own problem if you let them.

---

## 10. Testing the whole flow

Before announcing anything, do this on a clean machine.

1. **Create your keypair** and paste the public key into `config.py`.
2. **Build**, and confirm licensing is on: `401k-finder.exe license status`
   should say *"Not activated"* and print a Machine ID.
3. **Install on a clean VM** with no Python.
4. **Check the activation window**: the Machine ID is visible, Copy works, and
   *Email us for a licence…* opens a message with the ID already in it.
5. **Issue a key** with `--email` and check the reply reads well.
6. **Paste and activate.** It should succeed instantly, with no network.
7. **Restart, offline.** It must still start.
8. **Try the same key on a second machine.** It must be refused, naming the
   reason.
9. **Issue an expiring key** with `--days 1`, set the machine clock forward, and
   confirm the application refuses to start and says why.
10. **Confirm the data still works.** Download a form year and run a search.
    Licensing must not have broken the actual product.

Step 8 is the one that decides whether you have a product or a giveaway.
