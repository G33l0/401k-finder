# 401K Finder Pro: finding who holds your retirement money

A guide for anyone trying to track down a 401(k), 403(b) or pension from a job
they have left.

You do not need to understand pensions to use this. You need the names of the
employers you worked for.

---

## Contents

1. [What this can and cannot tell you](#1-what-this-can-and-cannot-tell-you)
2. [Before you start: load some data](#2-before-you-start-load-some-data)
3. [The quickest route: Find my accounts](#3-the-quickest-route-find-my-accounts)
4. [Reading the result](#4-reading-the-result)
5. [Finding the plan yourself: Find plans](#5-finding-the-plan-yourself-find-plans)
6. [Who to call, and what to say](#6-who-to-call-and-what-to-say)
7. [When the firm has changed hands](#7-when-the-firm-has-changed-hands)
8. [Looking a provider up directly](#8-looking-a-provider-up-directly)
9. [When nothing is found](#9-when-nothing-is-found)
10. [Places that search by Social Security number](#10-places-that-search-by-social-security-number)
11. [Keeping your data safe](#11-keeping-your-data-safe)
12. [Common questions](#12-common-questions)

---

## 1. What this can and cannot tell you

Every employer-sponsored retirement plan covered by ERISA files a **Form 5500**
with the U.S. Department of Labor each year, and those filings are public. This
application downloads them and makes them searchable on your own computer.

**What it tells you**

- The exact plan your employer ran: its legal name, its EIN, its plan number.
- The firm that held the money, **in the years you worked there**, which is
  often not the firm holding it today.
- Whether the plan still exists, was wound up, or was merged into another plan,
  and which plan received the money.
- A telephone number and website for the larger providers.
- A letter you can send, with the plan's details already filled in.

**What it cannot tell you**

It cannot tell you whether you personally have a balance, or how much.

Form 5500 is what an employer files **about a plan**, not about the people in
it. Across all 448 published record layouts there is no participant name, no
Social Security number and no individual balance anywhere. Every participant
figure in the filings is a count or a total for the whole plan.

That is not a limitation of this software and no amount of engineering changes
it. What this gives you is the plan's exact identity and the name of whoever
can look you up. That is the thing you cannot get anywhere else, and it is what
every recordkeeper will ask for first.

**Plans that never appear at all.** Some retirement accounts are outside this
dataset no matter how well the search works:

- **Governmental 457(b) plans**, which are exempt from filing.
- **Church plans** that have not elected ERISA coverage.
- **Solo 401(k) and one-participant plans**, which file Form 5500-EZ with the
  IRS. That is not public.
- **IRAs**, including SEP and SIMPLE plans funded through individual IRAs.

If your old job was with a state, a city, a school district or a church, go
straight to section 10.

---

## 2. Before you start: load some data

The application arrives empty. Open the **Data** tab.

**If you are only looking for your own accounts, press "Index every year".**

If you already have data loaded from an earlier version, note that the
telephone numbers filed on the forms are only picked up on import. Existing
data keeps working; re-import a year to fill them in.

This downloads just the two filing forms for every published year, 2009 to
2025. It is enough to match an employer to a plan across a whole career, and it
is a fraction of the size of the full data. Expect a substantial download the
first time, but nothing like the full set.

**To see who held the money, you then need the full year.** The firms are named
on the schedules, not on the main form, so an indexed year can tell you *which
plan* your employer ran but not *who held it*. Once the trace tells you which
years matter, come back to the Data tab, pick one of those years, and press
**Download and import**. Each full year is 20 to 60 GB.

You can keep using the application while a download runs, and cancel at any
point. An interrupted download resumes where it stopped.

**If your disk is too small.** Under *Where the data is kept* you can move
everything to an external or USB drive. The drive must be formatted exFAT or
NTFS: a FAT32 stick cannot hold a file large enough and will be refused.
Connect the drive before opening the application, and close the application
before ejecting it.

---

## 3. The quickest route: Find my accounts

Open the **Find my accounts** tab.

Fill in one row per employer you have worked for:

| Column | What to put |
|---|---|
| **Employer** | The company name. This is the only column that is required. |
| **City** | Optional. Helps when a name is common. |
| **State** | Two letters, such as `TX`. Improves the match a lot. |
| **From** / **To** | The years you worked there, roughly. Best guesses are fine. |

Press **Add row** for each additional job, then **Find my accounts**.

**Tips that make a real difference**

- Use the name on your **payslip or W-2**, not the shop sign. Plans are filed
  under the legal entity, so "Acme Manufacturing Inc" finds what "Acme" may not.
- If the company was bought, try both the old and new names as separate rows.
  A plan often keeps filing under the old name for years after a sale.
- Rough years are better than no years. They are what separates the firm that
  held your money from the one that holds it now.
- **Never type a Social Security number.** There is nothing here to match it
  against. The application will refuse it and tell you so.

---

## 4. Reading the result

For each job you get the plans that could cover it, strongest match first.

**Confidence** is how well the employer you typed matches the sponsor on the
filing, and whether the years line up. `STRONG` means the name matched and the
plan was filed for the years you were there.

**Holding the money while you were there** is the section that matters. It
lists each firm, its role, and the years it was filed for that plan.

The roles, in the order they are useful to you:

| Role | What it means for you |
|---|---|
| **Recordkeeper** | Keeps the individual account records. **This is who can look you up.** |
| **Trustee** / **Custodian** | Holds the assets. Can usually redirect you. |
| **Insurer** | The plan is an annuity contract. Common in 403(b) plans. Call them. |
| **Third-party administrator** | Runs the plan for the employer. A good second call. |
| **Plan administrator** | Legally obliged to answer a written request from a participant. Often the only telephone number a small plan files. |
| Accountant, actuary, preparer, attorney | Advisers. They cannot help you find your money. |

Every line says which schedule and field it came from and for which year, so
you can check any of it against the original filing.

Underneath each firm you may see a **telephone number and website**. Read
section 6 before using them.

---

## 5. Finding the plan yourself: Find plans

Use this tab when you know the employer and want to look at the plan directly,
or when **Find my accounts** returned several possibilities.

Type the employer name, or an EIN such as `12-3456789`, and press **Search**.

The results table includes:

- **Recordkeeper** and **Trustee / Custodian**, each with the years filed.
- **Service providers by year**, listing every firm and the years it covered.
- **Contact**, the telephone and website for whichever firm is most likely to
  be able to look you up.

Hover over any of those columns for the full list, including firms that were
taken over.

Click a plan to open it below, then choose the **Providers** tab for the
complete picture: every firm, the years, what it was paid, the service codes it
reported, and its contact details.

Underneath the firms, **Also filed for this plan** lists telephone numbers the
employer filed for people who are not service providers. The plan
administrator is the one that matters: they must answer a written request from
a participant.

The **Evidence** tab shows the exact filing behind every statement, down to the
file and row.

---

## 6. Who to call, and what to say

**Start with the recordkeeper.** If there is no recordkeeper, call the trustee,
the custodian or the insurer. If none of those is named, call the plan
administrator, who by law must respond to a written request from a participant.

**Have these ready before you call.** They are the first things you will be
asked, and having them is what separates a five-minute call from a dead end:

- The **plan name**, exactly as shown.
- The **EIN** and **plan number**, for example `12-3456789 / 001`.
- The **years you worked there**.
- Your Social Security number, to give **on the call**, never in an email.

**About the telephone numbers.** Some are filed and some are not, and the
application always says which.

A number labelled **(filed)** came from the filing itself, and cites the exact
field it was read from. Employers file the plan administrator's number, their
own, and for a small plan the trustee or custodian's. These are the best
numbers you can have: the employer filed them under penalty, and they reach
that plan's own office rather than a national queue.

Every other number, and every website, is **added by this application**. No DOL
dataset holds a website at all, so those come from a list of the larger
providers that ships with the software.

**Check the number on the firm's own website before you call.** Type the
website address into your browser yourself. Numbers change, and calling a
number that has been reassigned while carrying your Social Security number is
exactly the risk worth avoiding.

**Sending a letter.** Press **Save report** in the Find my accounts tab and
choose to include letters. You get a ready-to-send letter per plan with the
name, EIN and plan number filled in, citing your right under ERISA to a
statement of your accrued benefit. It deliberately does not include your Social
Security number, and says you will supply it through whatever secure channel
they prefer.

---

## 7. When the firm has changed hands

This is the most common reason a trail goes cold, and it is not a dead end.

Retirement businesses are bought and sold, and the buyer inherits the records.
A filing from 2012 naming a firm that no longer exists still tells you exactly
where to go, once you know who took it over. The application knows the larger
moves and says so on the provider:

| If a filing names | The records are now with |
|---|---|
| Prudential Retirement | Empower, from 2022 |
| MassMutual retirement plans | Empower, from 2021 |
| Great-West | Empower |
| Wells Fargo institutional retirement | Principal, from 2019 |
| ING U.S. | Voya, renamed in 2014 |
| Newport Group | Ascensus, from 2022 |
| AXA Equitable | Equitable, renamed in 2020 |

If the plan itself was wound up rather than the provider being bought, the
report follows that too. Where the final filing recorded a transfer, it names
the plan that received the assets and, if that plan is in your data, who
administers it now.

---

## 8. Looking a provider up directly

Open the **Providers** tab.

Type a firm's name and select it. Underneath you get **every company and plan
that names it**, with the role, the years, the participant count and the plan
assets. The contact details for that firm sit above the list.

This is useful in two ways:

- **You remember the provider but not the employer.** "My statements came from
  Empower" narrows the field fast, especially combined with the state.
- **You want to check you have the right firm.** Seeing the other companies it
  serves, and their size, tells you quickly whether this is the national
  recordkeeper you were thinking of or a small local firm with a similar name.

The search matches every spelling a firm was filed under, so one selection
covers the several different names the same company may appear as.

Double-click a provider to open its plans in the **Find plans** tab with the
filter already applied.

---

## 9. When nothing is found

A blank result is not proof that there was no plan. In order of likelihood:

1. **The years you worked there are not loaded.** This is by far the most
   common cause. The report tells you which years it searched. Load the missing
   ones from the Data tab and run it again.
2. **The employer filed under a different legal name.** Try the name on your
   W-2, the parent company, and any former name.
3. **The plan was too small to appear the way you expect.** Plans with fewer
   than 100 participants file the shorter Form 5500-SF. It is searched too, but
   it names fewer firms: often only a trustee.
4. **The employer never had to file.** Government, church and one-participant
   plans are outside this dataset entirely.
5. **You are searching an indexed year rather than a full one.** The plan will
   be found but no provider will be named. The report says when a year is thin
   rather than letting it look empty.

---

## 10. Places that search by Social Security number

This application cannot confirm an account exists in your name. These can. They
hold participant-level records and are the only places your Social Security
number belongs.

They are listed in full at the end of every saved report, with what each holds
and what it needs, and in the **Find my accounts** tab.

- **Retirement Savings Lost and Found**, run by the Department of Labor. New,
  and built from data plans have only recently had to report, so an older
  account may not appear yet.
- **National Registry of Unclaimed Retirement Benefits.** Private and
  voluntary: a plan appears only if its administrator chose to list it.
- **Social Security Administration.** Holds notices from Form 8955-SSA, which
  plans file listing people who left with a vested benefit. This is the one
  government record tying a person to a specific plan. No third party can
  search it for you; you have to ask SSA.
- **Your state's unclaimed property office.** Where small cashed-out balances
  and abandoned IRAs end up. Search every state you have lived or worked in.
- **EBSA Benefits Advisors**, free help from the Department of Labor, for when
  a plan will not respond to you.
- **EFAST2**, to read the original filings behind everything shown here.

**Two rules worth keeping.** Never send your Social Security number in an
email. Never give it to anyone who contacted you first. Reach these sites by
typing their address into your browser yourself.

---

## 11. Keeping your data safe

Everything runs on your computer. No search, no employer name and no report is
sent anywhere. The only network traffic is downloading the public filings from
the Department of Labor.

The work history you type is not saved unless you save it yourself.

The application will not accept a Social Security number anywhere, and refuses
one if you paste it in. There is nothing here to match it against, and asking
for one would make this look like the scams that operate in this area.

---

## 12. Common questions

**How far back does this go?**
Form years 2009 to 2025. For a job before 2009, the plan usually still exists
and still files, so search it anyway: a plan filing in 2015 under the same EIN
is the same plan you paid into in 2003.

**The plan says it was terminated. Is my money gone?**
No. When a plan winds up the money goes somewhere, and the filings usually say
where. If assets were transferred, the report names the receiving plan. If they
were not, the balance was most likely paid out or rolled into an IRA in your
name, which is exactly what the registries in section 10 are for.

**I found the plan but no provider is named.**
Either that year is indexed rather than fully loaded, or the plan filed the
short Form 5500-SF, which names fewer firms. Load the full year and look again.

**There are two firms listed for the same role in the same year.**
Plans do change provider mid-year, and some report the same engagement on two
schedules. Every line names its schedule and field, so you can tell which is
which. Contact the more recent one first.

**The telephone number did not work.**
If it was not marked *(filed)*, it came from the list that ships with the
software rather than from the filing, and firms change their numbers. Use the
website instead and find the current number there. If a *(filed)* number is
dead, the filing is simply old: try a more recent form year, or the plan
administrator.

**Can it find my IRA?**
No. IRAs file nothing with the Department of Labor. Section 10 is the route.

**Does an employer have to talk to me?**
The plan administrator must respond to a written request from a participant for
a statement of accrued benefits. If they do not, contact EBSA Benefits
Advisors, who will contact them on your behalf. That service is free.

---

*This application describes what public Form 5500 filings say. It is not
financial, legal or tax advice, and it is not confirmation that any account
exists in your name.*
