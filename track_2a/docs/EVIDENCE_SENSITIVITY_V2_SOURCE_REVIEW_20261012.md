# Evidence sensitivity v2: source review annex

AI-assisted independent evidence adjudication. This is not completed human verification, a human signature or evidence of inference quality. Page numbers below are one-based physical PDF pages and printed pages; offsets are zero-based half-open ranges into the identified `pdftotext` page text. Line breaks, ligatures and soft hyphens are preserved exactly. The archived v1 distractors remain clipped as originally recorded; newly selected X passages are complete sentences/paragraphs or complete recommendations with source headings. A is deliberately preserved unchanged.

The JSON plan preserves exact quotations and provenance for all 34 historical distractors, 30 replacement distractors, and all B/adjudication spans. This annex displays the full reviewed quotations and a classification table for the original candidates. Necessary context headers form part of B and are moved together with it.

## Row 29: accepted

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `de`; source language: `fr`.

Claim:

Der Bundesrat spricht sich dafür aus, die Reform der beruflichen Vorsorge anzunehmen.

Direct Federal Council/Parliament pension-reform acceptance; DE claim faithfully matches FR.

Speaker/proposal: Conseil federal et Parlement; Reforme de la prevoyance professionnelle.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p22-c1 | 22; [0, 900) | `irrelevant` | replaced: Pension mechanics; recommendation absent. |
| p20-c1 | 20; [0, 900) | `irrelevant` | replaced: System background; recommendation absent. |

### B / adjudication evidence

**row29-B-1** - PDF/printed p.29; offsets [1005, 1138).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/iWYLyEPfLvhn/2024-09-22_explications_du_conseil_federal.pdf)

PDF SHA-256: `e6717534db788bf85e15bc505c5ab6f839cd61396be0f84a5aa035c767de8578`.

Speaker: Conseil federal et Parlement. Proposal: Reforme de la prevoyance professionnelle.

```text
Pour toutes ces raisons, le Conseil fédéral et le Parlement
vous recommandent d’accepter la réforme de la prévoyance
professionnelle.
```


### Replacement distractors

**row29-X-1** - PDF/printed p.22; offsets [465, 987).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/iWYLyEPfLvhn/2024-09-22_explications_du_conseil_federal.pdf)

PDF SHA-256: `e6717534db788bf85e15bc505c5ab6f839cd61396be0f84a5aa035c767de8578`.

Speaker: Federal explanatory text / ballot text. Proposal: Reforme de la prevoyance professionnelle.

Classification: `irrelevant`. Conversion-rate mechanics do not establish the attributed recommendation.

```text
La réforme s’attaque au problème de financement engendré par l’augmentation de l’espérance de vie et les rendements
trop faibles provenant des avoirs de vieillesse placés. Afin
de résoudre ce problème, le taux de conversion sera abaissé
de 6,8 % à 6,0 % pour la partie obligatoire de la prévoyance
professionnelle. Ce taux détermine le montant de la future
rente. Pour un avoir de vieillesse de 100 000 francs, la rente
annuelle s’élève actuellement à 6800 francs. Si la réforme est
acceptée, elle s’élèvera à 6000 francs.
```

**row29-X-2** - PDF/printed p.20; offsets [163, 1244).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/iWYLyEPfLvhn/2024-09-22_explications_du_conseil_federal.pdf)

PDF SHA-256: `e6717534db788bf85e15bc505c5ab6f839cd61396be0f84a5aa035c767de8578`.

Speaker: Federal explanatory text / ballot text. Proposal: Reforme de la prevoyance professionnelle.

Classification: `irrelevant`. Pension-system background; no acceptance recommendation.

```text
En Suisse, la prévoyance vieillesse repose sur trois piliers.
Le 1er pilier est la prévoyance étatique. Toutes les personnes qui
vivent ou travaillent en Suisse sont assurées à l’assurance-vieillesse
et survivants (AVS). Celle-ci répond aux besoins fondamentaux
de tous les retraités. Si la rente AVS ne suffit pas, les prestations
complémentaires permettent de couvrir les besoins vitaux.
Le 2e pilier est la prévoyance professionnelle. Avec l’AVS, il permet
aux retraités de maintenir de manière appropriée leur niveau de vie
antérieur. À cette fin, les actifs sont affiliés à une caisse de pension
à partir d’un certain revenu. La loi prescrit certaines prestations
minimales aux caisses de pension. La présente réforme concerne
uniquement ces prestations minimales, c’est-à-dire la partie obligatoire de la prévoyance professionnelle.
Le 3e pilier est la prévoyance privée. Les personnes actives peuvent
verser volontairement un certain montant sur un compte bancaire
spécial ou souscrire une assurance-vie. Le 3e pilier permet de couvrir
les besoins individuels à la retraite.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1035 | 268 | 705 | 705 | 437 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 119: accepted

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `de`; source language: `fr`.

Claim:

Der Zusammenfassung zufolge importiert die Schweiz rund 75 % ihrer Energie.

Approximately 75 percent of energy is explicitly imported; not an emissions target or tax share.

Speaker/proposal: En bref summary; Loi sur le climat et l’innovation.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p35-c2 | 35; [900, 1800) | `plausible_hard_negative` | replaced: Emission targets use 75 percent, not energy import. |
| p12-c2 | 12; [900, 1800) | `plausible_hard_negative` | replaced: Cantonal tax receipt share uses 75 percent, not energy import. |

### B / adjudication evidence

**row119-B-1** - PDF/printed p.6; offsets [3, 267).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/Lv5UWt6X1iUj/2023-06-18_explications_du_conseil_federal.pdf)

PDF SHA-256: `925a6f553a6f67059cebacccfa7d4efcffc3a31d5441d9c978a57546b6b8bdd6`.

Speaker: En bref summary. Proposal: Loi sur le climat et l’innovation.

```text
Deuxième objet : loi sur le climat et l’innovation

En bref

Loi fédérale sur les objectifs en
matière de protection du climat,
sur l’innovation et sur le ren­
forcement de la sécurité énergétique (contre-projet indirect
à l’initiative pour les glaciers)

Contexte
```

**row119-B-2** - PDF/printed p.6; offsets [269, 405).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/Lv5UWt6X1iUj/2023-06-18_explications_du_conseil_federal.pdf)

PDF SHA-256: `925a6f553a6f67059cebacccfa7d4efcffc3a31d5441d9c978a57546b6b8bdd6`.

Speaker: En bref summary. Proposal: Loi sur le climat et l’innovation.

```text
La Suisse importe environ 75 % de son énergie. Le pétrole
et le gaz naturel consommés en Suisse proviennent exclusivement de l’étranger.
```


### Replacement distractors

**row119-X-1** - PDF/printed p.35; offsets [818, 1343).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/Lv5UWt6X1iUj/2023-06-18_explications_du_conseil_federal.pdf)

PDF SHA-256: `925a6f553a6f67059cebacccfa7d4efcffc3a31d5441d9c978a57546b6b8bdd6`.

Speaker: Federal Assembly ballot text. Proposal: Loi sur le climat et l’innovation.

Classification: `plausible_hard_negative`. 75 percent is an emissions target, not the share of imported energy; all target conditions retained.

```text
3 La Confédération veille à ce que les émissions de gaz à effet de serre soient réduites par rapport à 1990; les objectifs intermédiaires sont les suivants:

a.

entre 2031 et 2040: d’au moins 64 % en moyenne;

b.

jusqu’en 2040: d’au moins 75 %;

c.

entre 2041 et 2050: d’au moins 89 % en moyenne.

4 Les objectifs de réduction doivent être réalisables sur le plan de la technique et

économiquement supportables. Dans la mesure du possible, ils doivent être atteints
grâce à des réductions d’émissions réalisées en Suisse.
```

**row119-X-2** - PDF/printed p.12; offsets [1365, 1953).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/Lv5UWt6X1iUj/2023-06-18_explications_du_conseil_federal.pdf)

PDF SHA-256: `925a6f553a6f67059cebacccfa7d4efcffc3a31d5441d9c978a57546b6b8bdd6`.

Speaker: Federal explanatory text / ballot text. Proposal: OECD/G20 minimum taxation.

Classification: `plausible_hard_negative`. 75 percent refers to cantonal tax receipts, not energy imports; ordinance-only scope retained.

```text
La disposition transitoire relative à la mise en œuvre de
l’imposition minimale fixe en particulier les principes suivants
devant être observés par le Conseil fédéral dans son
ordonnance :
–	la Confédération perçoit un impôt complémentaire pour
combler l’écart entre le taux d’imposition minimal de
15 % et un taux d’imposition plus bas ;
–	les cantons reçoivent 75 % des recettes de l’impôt
complémentaire et la Confédération, 25 %.
Ces principes ne s’appliquent qu’à l’ordonnance. Dans la
loi, le Conseil fédéral et le Parlement pourront régler la mise
en œuvre de manière différente.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1370 | 337 | 655 | 655 | 318 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 297: revised

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `fr`; source language: `fr`.

Claim:

Le comité estime que les PME ne disposent pas des ressources financières et organisationnelles nécessaires pour instaurer un congé de paternité de deux semaines, les remplacements de courte durée étant coûteux et complexes.

Committee attribution added to rendered B; complete two-week resource and costly/complex replacement causal sentence retained. This supports what the committee claims, not its objective truth.

Speaker/proposal: Comite referendaire; Conge de paternite.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p65-c1 | 65; [0, 900) | `plausible_hard_negative` | replaced: Institutional opposing rationale is a different speaker; truncated tail requires replacement. |
| p10-c1 | 10; [0, 900) | `irrelevant` | replaced: Leave design, not committee resource assessment. |

### B / adjudication evidence

**row297-B-1** - PDF/printed p.62; offsets [4, 72).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/XuiMCko39BzI/2020-09-27_explications_du_conseil_federal.pdf)

PDF SHA-256: `8e3c67fd515a7438d1ec687be65001c01a0ece56eb952fdd23f9ca23c8393355`.

Speaker: Comite referendaire. Proposal: Conge de paternite.

```text
Quatrième objet : congé de paternité

Arguments

Comité référendaire
```

**row297-B-2** - PDF/printed p.62; offsets [1290, 1470).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/XuiMCko39BzI/2020-09-27_explications_du_conseil_federal.pdf)

PDF SHA-256: `8e3c67fd515a7438d1ec687be65001c01a0ece56eb952fdd23f9ca23c8393355`.

Speaker: Comite referendaire. Proposal: Conge de paternite.

```text
Les PME n’ont les moyens ni ﬁnanciers ni organisationnels
de mettre en place un congé de paternité de deux semaines,
car les remplacements de courte durée sont chers et compliqués.
```


### Replacement distractors

**row297-X-1** - PDF/printed p.65; offsets [679, 888).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/XuiMCko39BzI/2020-09-27_explications_du_conseil_federal.pdf)

PDF SHA-256: `8e3c67fd515a7438d1ec687be65001c01a0ece56eb952fdd23f9ca23c8393355`.

Speaker: Federal Council and Parliament. Proposal: Conge de paternite.

Classification: `plausible_hard_negative`. Council/Parliament acceptance is a different speaker and does not deny what the referendum committee claims.

```text
Recommandation
du Conseil fédéral
et du Parlement

Pour toutes ces raisons, le Conseil fédéral et le Parlement
vous recommandent d’accepter la modiﬁcation de la loi sur les
allocations pour perte de gain.

Oui
```

**row297-X-2** - PDF/printed p.10; offsets [248, 426).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/XuiMCko39BzI/2020-09-27_explications_du_conseil_federal.pdf)

PDF SHA-256: `8e3c67fd515a7438d1ec687be65001c01a0ece56eb952fdd23f9ca23c8393355`.

Speaker: Federal explanatory text / ballot text. Proposal: Conge de paternite.

Classification: `irrelevant`. Current leave entitlement does not establish the committee causal resource claim.

```text
La loi offre aux mères actives un congé de maternité payé
de quatorze semaines lors de la naissance d’un enfant. Les pères
n’ont en revanche droit qu’à un ou deux jours de congé.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1254 | 333 | 446 | 446 | 113 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 432: revised

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `it`; source language: `it`.

Claim:

Il comitato afferma che la donazione di sperma alle coppie lesbiche viola l’articolo 119 della Costituzione federale, perché trasforma la procreazione assistita da eccezione medica in norma di legge, sacrificando il diritto del bambino a conoscere ed essere accudito da entrambi i genitori biologici.

Committee/proposal heading plus both constitutional and child-right excerpts retained, including medical exception, infertility/serious-disease conditions and age-18 qualification. This is an attributed stakeholder claim, not an independently established constitutional violation.

Speaker/proposal: Comitati referendari; Matrimonio per tutti.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p29-c1 | 29; [0, 900) | `ambiguous_or_decisive` | replaced: Opposing legal/right assessment without source speaker in rendered excerpt creates attribution ambiguity. |
| p32-c1 | 32; [0, 900) | `ambiguous_or_decisive` | replaced: Starts inside a legal parental-status condition; cannot adjudicate truncated scope. |

### B / adjudication evidence

**row432-B-1** - PDF/printed p.26; offsets [4, 78).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/NJXQlhZXHqDA/2021-09-26_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `d01075b2fabc1609d8c7e2b5ede595286c504d35ea4947b1fa0709fddbb63538`.

Speaker: Comitati referendari. Proposal: Matrimonio per tutti.

```text
Gli
argomenti

Secondo oggetto: Matrimonio per tutti

Comitati referendari
```

**row432-B-2** - PDF/printed p.26; offsets [1638, 2099).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/NJXQlhZXHqDA/2021-09-26_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `d01075b2fabc1609d8c7e2b5ede595286c504d35ea4947b1fa0709fddbb63538`.

Speaker: Comitati referendari. Proposal: Matrimonio per tutti.

```text
Contrariamente all’intenzione originaria del Consiglio
federale, la presente legge prevede anche la donazione di
sperma a favore delle coppie lesbiche. Il «Matrimonio civile per
tutti» viola quindi l’articolo 119 Cost., che anche per le coppie
eterosessuali consente la procreazione assistita soltanto in caso
di infecondità o per sventare il pericolo di una malattia grave.
Classiﬁcare le coppie lesbiche come infeconde contraddice
tutte le deﬁnizioni vigenti.
```

**row432-B-3** - PDF/printed p.27; offsets [42, 655).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/NJXQlhZXHqDA/2021-09-26_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `d01075b2fabc1609d8c7e2b5ede595286c504d35ea4947b1fa0709fddbb63538`.

Speaker: Comitati referendari. Proposal: Matrimonio per tutti.

```text
Da eccezione medica la donazione di sperma diventa regola
prevista dalla legge, senza considerare le conseguenze per il
bambino. Il diritto di conoscere e di essere accudito da entrambi i genitori biologici gli è in linea di principio negato ﬁno al
compimento dei 18 anni. Per la formazione dell’identità di un
bambino, il radicamento nella famiglia d’origine è fondamentale. Per questo la donazione di sperma deve restare un’ecce zione. I bambini hanno bisogno di modelli di ruolo rappresentati dai due sessi; la donazione di sperma a favore delle coppie
lesbiche, invece, li priva per legge della ﬁgura paterna.
```


### Replacement distractors

**row432-X-1** - PDF/printed p.28; offsets [4, 666).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/NJXQlhZXHqDA/2021-09-26_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `d01075b2fabc1609d8c7e2b5ede595286c504d35ea4947b1fa0709fddbb63538`.

Speaker: Federal Council and Parliament. Proposal: Matrimonio per tutti.

Classification: `plausible_hard_negative`. Explicitly institutional individual-liberty argument; does not adjudicate the committee Article 119/biological-parent claim.

```text
Secondo oggetto: Matrimonio per tutti

Gli
argomenti

Consiglio federale e Parlamento

Libertà individuali

Lo Stato non può imporre alle persone come organizzare
la loro vita privata e familiare. Una coppia deve essere libera
di decidere se e come intende regolare legalmente la propria
relazione. Già oggi esistono comunioni di vita formate da
coppie dello stesso sesso, con o senza ﬁgli. Tali coppie non
possono però sposarsi, ma solo contrarre un’unione domestica
registrata. Questo tipo di unione non è tuttavia del tutto
equivalente al matrimonio. L’apertura del matrimonio permette di eliminare questa disparità di trattamento, senza svantaggiare nessuno.
```

**row432-X-2** - PDF/printed p.32; offsets [733, 1139).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/NJXQlhZXHqDA/2021-09-26_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `d01075b2fabc1609d8c7e2b5ede595286c504d35ea4947b1fa0709fddbb63538`.

Speaker: Federal explanatory text / ballot text. Proposal: Matrimonio per tutti.

Classification: `irrelevant`. Complete property-regime clause concerns a different legal issue.

```text
1 Alle coppie di persone dello stesso sesso che hanno contratto matri-

monio all’estero prima dell’entrata in vigore integrale della modifica
del presente Codice del 18 dicembre 2020 si applica retroattivamente,
dalla data della celebrazione del matrimonio, il regime ordinario della
partecipazione agli acquisti, in quanto esse non abbiano altrimenti disposto per convenzione matrimoniale o patrimoniale.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1401 | 619 | 895 | 895 | 276 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 442: accepted

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `it`; source language: `de`.

Claim:

Il riassunto dichiara che l’uso della E-ID è facoltativo e non comporta costi.

Use is voluntary and free; online application free, canton may charge in-person identification; future obligation would require statutory change and possible referendum. The claim concerns use, not universal free acquisition.

Speaker/proposal: En bref/explanatory text; E-ID-Gesetz.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p28-c1 | 28; [0, 900) | `plausible_hard_negative` | replaced: Attributed security critique unrelated to free optional use. |
| p28-c2 | 28; [900, 1800) | `ambiguous_or_decisive` | replaced: Starts mid-word; voluntariness critique lacks speaker attribution in this block. |

### B / adjudication evidence

**row442-B-1** - PDF/printed p.26; offsets [71, 837).

[Official PDF](https://www.bk.admin.ch/dam/de/sd-web/6DaWglL-N7NM/2025-09-28_erlaeuterungen_des_bundesrates.pdf)

PDF SHA-256: `39c020145299913685e4d0b6899fa23bb1f94938652a417e0c1da08d316ade8a`.

Speaker: En bref/explanatory text. Proposal: E-ID-Gesetz.

```text
Alle Einwohnerinnen und Einwohner der Schweiz sowie
Auslandschweizerinnen und -schweizer können die E-ID beantragen. Es gibt aber keine Verpflichtung, die E-ID zu nutzen.
Der Bund bietet sämtliche Dienstleistungen weiterhin auch
analog an. Es bräuchte eine Gesetzesänderung, wenn man die
E-ID in Zukunft in gewissen Fällen für obligatorisch erklären
möchte. Darüber entscheidet das Parlament und dagegen
könnte das Referendum ergriffen werden. Die E-ID ist Teil des
Service public und nicht gewinnorientiert. Sie kann online
gratis beantragt werden. An einem Schalter, zum Beispiel
in einem Passbüro, können die Kantone eine Gebühr für die
Personenidentifikation verlangen. Diese Identifikation ist
nötig, um die E-ID zu erhalten. Die Nutzung der E-ID ist
kostenlos.
```


### Replacement distractors

**row442-X-1** - PDF/printed p.28; offsets [4, 375).

[Official PDF](https://www.bk.admin.ch/dam/de/sd-web/6DaWglL-N7NM/2025-09-28_erlaeuterungen_des_bundesrates.pdf)

PDF SHA-256: `39c020145299913685e4d0b6899fa23bb1f94938652a417e0c1da08d316ade8a`.

Speaker: Referendum committee E-ID-Gesetz-Nein. Proposal: E-ID-Gesetz.

Classification: `plausible_hard_negative`. Attributed referendum-committee security objection; no usage price or voluntariness finding.

```text
Zweite Vorlage: E-ID-Gesetz

Argumente

Referendumskomitees
Komitee «E-ID-Gesetz-Nein»

Unsicherer
digitaler
Schweizerpass

Das neue E-ID-Gesetz wiederholt Fehler von 2021, als die
Schweizer Bevölkerung einen unsicheren digitalen Schweizerpass (E-ID) primär aufgrund von Datenschutzbedenken ablehnte. Auch das neue Gesetz schafft keine ausreichenden
Sicherheitsgarantien.
```

**row442-X-2** - PDF/printed p.4; offsets [146, 733).

[Official PDF](https://www.bk.admin.ch/dam/de/sd-web/6DaWglL-N7NM/2025-09-28_erlaeuterungen_des_bundesrates.pdf)

PDF SHA-256: `39c020145299913685e4d0b6899fa23bb1f94938652a417e0c1da08d316ade8a`.

Speaker: Federal explanatory summary. Proposal: Liegenschaftssteuer auf Zweitliegenschaften.

Classification: `irrelevant`. Abolition of imputed rent on dwellings, unrelated to E-ID use.

```text
Wer eine Liegenschaft besitzt und diese selbst nutzt, muss
den sogenannten Eigenmietwert als Einkommen versteuern. Im
Gegenzug können Schuldzinsen und die Kosten für den Unterhalt vom Einkommen abgezogen werden. Das Parlament hat
eine Gesetzesänderung verabschiedet, die die Besteuerung des
Eigenmietwerts abschafft und die Abzugsmöglichkeiten einschränkt. Das gilt für Erst- und Zweitliegenschaften. Gleichzeitig
hat es eine Verfassungsänderung beschlossen, die es den Kantonen erlaubt, eine besondere Liegenschaftssteuer auf überwiegend selbstgenutzten Zweitliegenschaften einzuführen.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1321 | 433 | 695 | 695 | 262 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 455: disputed

Primary analysis: **excluded**. Dataset gold remains `entailment`. Claim language: `it`; source language: `fr`.

Claim:

Secondo il testo di voto, le imprese devono dimostrare di aver esercitato una ragionevole diligenza, analizzando le ripercussioni effettive e potenziali sui diritti umani riconosciuti a livello internazionale e sull’ambiente, adottando misure adeguate per prevenire le violazioni, porre fine a quelle esistenti e riferire sulle misure adottate.

Gold disagreement: IT devono dimostrare implies an unconditional proof obligation. Article 101a(2)(b) requires exercising reasonable diligence; (2)(c) gives proof of diligence OR unavoidable damage as alternative liability defences. These are not identical obligations. Excluded from primary analysis; dataset entailment unchanged.

Speaker/proposal: Initiative text summary; Entreprises responsables.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p18-c1 | 18; [0, 900) | `ambiguous_or_decisive` | excluded_with_case: Ballot Article 101a is necessary to resolve the disputed claim; fragment ends before duties. |
| p14-c2 | 14; [900, 1800) | `ambiguous_or_decisive` | excluded_with_case: Liability defence changes claim scope and cannot serve as irrelevant distraction. |

### B / adjudication evidence

**row455-B-1** - PDF/printed p.18; offsets [49, 211).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/ywovGJwC1GeO/2020-11-29_explications_du_conseil_federal.pdf)

PDF SHA-256: `62870b79f34f5d9af48ca53709090140403133edc23ef393bf7b17bcdd35c48f`.

Speaker: Initiative text summary. Proposal: Entreprises responsables.

```text
Texte soumis au vote
Arrêté fédéral relatif à
l’initiative populaire « Entreprises responsables –
pour protéger l’être humain et l’environnement »
du 19 juin 2020
```

**row455-B-2** - PDF/printed p.18; offsets [927, 1873).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/ywovGJwC1GeO/2020-11-29_explications_du_conseil_federal.pdf)

PDF SHA-256: `62870b79f34f5d9af48ca53709090140403133edc23ef393bf7b17bcdd35c48f`.

Speaker: Initiative text summary. Proposal: Entreprises responsables.

```text
2 La loi règle les obligations des entreprises qui ont leur siège statutaire, leur admi-

nistration centrale ou leur établissement principal en Suisse, conformément aux
principes suivants:

1
2
3

a.

les entreprises doivent respecter également à l’étranger les droits de
l’homme internationalement reconnus et les normes environnementales internationales; elles doivent veiller à ce que ces droits et ces normes soient
également respectés par les entreprises qu’elles contrôlent; les rapports effectifs déterminent si une entreprise en contrôle une autre; un contrôle peut
de fait également être exercé par le biais d’un pouvoir économique;

b.

les entreprises sont tenues de faire preuve d’une diligence raisonnable; elles
doivent notamment examiner quelles sont les répercussions effectives et potentielles sur les droits de l’homme internationalement reconnus et sur
l’environnement, prendre des mesures appropriées en vue de prévenir toute
```

**row455-B-3** - PDF/printed p.19; offsets [7, 1111).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/ywovGJwC1GeO/2020-11-29_explications_du_conseil_federal.pdf)

PDF SHA-256: `62870b79f34f5d9af48ca53709090140403133edc23ef393bf7b17bcdd35c48f`.

Speaker: Initiative text summary. Proposal: Entreprises responsables.

```text
violation des droits de l’homme internationalement reconnus et des normes
environnementales internationales, mettre fin aux violations existantes et
rendre compte des mesures prises; ces obligations s’appliquent aux entreprises contrôlées ainsi qu’à l’ensemble des relations d’affaires; l’étendue de
cette diligence raisonnable est fonction des risques s’agissant des droits de
l’homme et de l’environnement; lorsqu’il règle l’obligation de diligence raisonnable, le législateur tient compte des besoins des petites et moyennes entreprises qui ne présentent de tels risques que dans une moindre mesure;
c.

les entreprises sont également responsables du dommage causé par les entreprises qu’elles contrôlent lorsque celles-ci violent des droits de l’homme
internationalement reconnus ou des normes environnementales internationales dans l’accomplissement de leur activité; elles ne le sont pas au sens de
la présente disposition si elles prouvent qu’elles ont fait preuve de toute la
diligence prévue à la let. b pour prévenir le dommage ou que leur diligence
n’eût pas empêché le dommage de se produire;
```


### Replacement distractors

No C/D evidence or inference planned for this excluded case.

## Row 1026: revised

Primary analysis: **retained**. Dataset gold remains `contradiction`. Claim language: `de`; source language: `it`.

Claim:

Laut der Zusammenfassung wurden die finanziellen Hilfen auf Personen begrenzt, die bereits genügend Unterstützung erhalten hatten.

Replaced p31 with p8 summary explicitly extending assistance to insufficient/no previous support; directly contradicts DE limited-to-sufficiently-supported claim.

Speaker/proposal: En bref/project description; Modifica della legge COVID-19.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p45-c2 | 45; [900, 1800) | `ambiguous_or_decisive` | replaced: Truncated financial-assistance legal conditions undermine contrast. |
| p43-c1 | 43; [0, 900) | `ambiguous_or_decisive` | replaced: Eligibility/equal-treatment provisions may bear on scope and are truncated. |

### B / adjudication evidence

**row1026-B-1** - PDF/printed p.8; offsets [3, 56).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: En bref/project description. Proposal: Modifica della legge COVID-19.

```text
Terzo oggetto: Modiﬁca della legge COVID-19

In breve
```

**row1026-B-2** - PDF/printed p.8; offsets [965, 1133).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: En bref/project description. Proposal: Modifica della legge COVID-19.

```text
Con la modiﬁca legislativa del marzo 2021, il Parlamento
ha esteso gli aiuti ﬁnanziari a chi aveva ricevuto un sostegno
troppo limitato o non ne aveva ricevuto nessuno.
```


### Replacement distractors

**row1026-X-1** - PDF/printed p.45; offsets [1336, 1704).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: Federal explanatory text / ballot text. Proposal: Modifica della legge COVID-19.

Classification: `irrelevant`. Advance-payment processing threshold does not specify prior-support eligibility.

```text
Art. 17d

Concessione di anticipi

Se una richiesta di aiuti COVID-19 (indennità per lavoro ridotto, casi di rigore, aiuti
settoriali) non può essere trattata entro 30 giorni perché il calcolo della pretesa è reso
difficoltoso dalla natura stessa delle attività dell’avente diritto, le autorità competenti
possono concedere anticipi secondo una procedura semplificata.
```

**row1026-X-2** - PDF/printed p.38; offsets [1443, 1834).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: Federal explanatory text / ballot text. Proposal: COVID-19 political-rights provision.

Classification: `irrelevant`. Political-rights attestation provision, not financial-aid recipients.

```text
Art. 2 cpv. 1
1 Per agevolare l’esercizio dei diritti politici, il Consiglio federale può prevedere che

le domande di referendum e le iniziative popolari debbano essere depositate presso
la Cancelleria federale entro la scadenza del termine di referendum o di deposito
dell’iniziativa popolare con il necessario numero di firme ma possano essere prive
dell’attestazione del diritto di voto.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1488 | 320 | 533 | 533 | 213 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 1178: revised

Primary analysis: **retained**. Dataset gold remains `contradiction`. Claim language: `fr`; source language: `fr`.

Claim:

Le Conseil fédéral recommande d’accepter l’initiative populaire en faveur d’une eau potable propre et d’une alimentation saine.

Direct Council/Parliament rejection of clean-drinking-water initiative. Corroborating p16 distractor replaced.

Speaker/proposal: Conseil federal et Parlement; Initiative eau potable propre.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p16-c1 | 16; [0, 900) | `corroborating` | replaced: Parliament rejection independently corroborates the gold rejection. |
| p18-c1 | 18; [0, 408) | `irrelevant` | replaced: Proposal title/contents, without stance. |

### B / adjudication evidence

**row1178-B-1** - PDF/printed p.25; offsets [1298, 1464).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/UxUxfYD5ma0h/2021-06-13_explications_du_conseil_federal.pdf)

PDF SHA-256: `65c54df2537b8ab9d6e155c0e602d6bc2379e47741004bc66565064d0aee4ab4`.

Speaker: Conseil federal et Parlement. Proposal: Initiative eau potable propre.

```text
Pour toutes ces raisons, le Conseil fédéral et le Parlement
vous recommandent de rejeter l’initiative populaire pour une
eau potable propre et une alimentation saine.
```


### Replacement distractors

**row1178-X-1** - PDF/printed p.22; offsets [4, 635).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/UxUxfYD5ma0h/2021-06-13_explications_du_conseil_federal.pdf)

PDF SHA-256: `65c54df2537b8ab9d6e155c0e602d6bc2379e47741004bc66565064d0aee4ab4`.

Speaker: Initiative committee. Proposal: Initiative eau potable propre.

Classification: `plausible_hard_negative`. Initiative committee advocates change; not Federal Council rejection or acceptance.

```text
Premier objet : initiative pour une eau potable propre

Arguments

Comité d’initiative
Avoir de l’eau potable propre est un droit fondamental que
viole la politique agricole actuelle. L’usage massif de pesticides, l’utilisation exagérée d’antibiotiques dans l’élevage et
l’épandage excessif de lisier dans les champs menacent notre
eau potable. Il est choquant que ces dommages écologiques
et ces risques pour la santé soient financés par des milliards
de francs de subventions provenant de nos impôts. Cela doit
cesser. Il faut absolument réorienter les subventions. C’est
ce que va faire l’initiative pour une eau potable propre.
```

**row1178-X-2** - PDF/printed p.8; offsets [3, 873).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/UxUxfYD5ma0h/2021-06-13_explications_du_conseil_federal.pdf)

PDF SHA-256: `65c54df2537b8ab9d6e155c0e602d6bc2379e47741004bc66565064d0aee4ab4`.

Speaker: Federal explanatory text / ballot text. Proposal: COVID-19 Act.

Classification: `irrelevant`. COVID-19 legislative chronology, unrelated to drinking-water recommendation.

```text
Troisième objet : loi COVID-19

En bref

Loi COVID-19

Contexte

La pandémie de COVID-19 a atteint la Suisse en février 2020.
Le nombre de personnes gravement malades augmentant rapidement, le Conseil fédéral a pris des mesures pour protéger
la population et soutenir les personnes et les entreprises qui
subissaient les conséquences économiques de la pandémie.
Le gouvernement devait agir vite. Étant donné que la loi sur les
épidémies ne contenait pas de base légale pour toutes les me sures, il a aussi recouru au droit de nécessité, comme le permet
la Constitution dans une telle situation de crise. La validité du
droit de nécessité étant limitée dans le temps, le Conseil fédé ral et le Parlement ont élaboré la loi COVID-19 pour prolonger
les mesures. Le Parlement l’a adoptée en septembre 2020 et l’a
déclarée urgente pour qu’elle entre en vigueur immédiatement.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1104 | 282 | 654 | 654 | 372 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 1344: revised

Primary analysis: **retained**. Dataset gold remains `contradiction`. Claim language: `it`; source language: `fr`.

Claim:

Secondo il testo di voto, le imprese che propongono film in Svizzera devono destinare ogni anno almeno il 10% delle loro entrate lorde alla produzione cinematografica indipendente svizzera, oppure versare una tassa sostitutiva equivalente.

Ballot Article 24b says 4 percent, not 10. Full replacement-tax trigger, four-year average, foreign-targeting extension and SSR exception retained.

Speaker/proposal: Texte soumis au vote, art. 24b; Loi sur le cinema.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p18-c1 | 18; [0, 900) | `irrelevant` | replaced: Policy approval does not decide percentage. |
| p12-c2 | 12; [900, 1646) | `corroborating` | replaced: Four-year test and replacement tax corroborate components of B; also starts mid-word. |

### B / adjudication evidence

**row1344-B-1** - PDF/printed p.22; offsets [42, 856).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/PCWaDg8-GOcJ/2022-05-15_explications_du_conseil_federal.pdf)

PDF SHA-256: `f9c5d7830a90b9af3b0c8fde853e036a14ca1b111958342bb39ad98576adc308`.

Speaker: Texte soumis au vote, art. 24b. Proposal: Loi sur le cinema.

```text
Section 2
Prise en compte de la création cinématographique suisse indépendante
Art. 24b

Principe

1 Les entreprises qui, en Suisse, proposent des films dans leur programmation ou par

le biais de services électroniques à la demande ou par abonnement doivent affecter
annuellement 4 % au moins de leurs recettes brutes à la création cinématographique
suisse indépendante ou payer une taxe de remplacement correspondante. Une taxe
de remplacement est exigible si la part des recettes devant être investie annuellement
n’est pas atteinte en moyenne sur une période de quatre ans.
2 L’obligation visée à l’al. 1 est également applicable aux entreprises qui ont leur

siège à l’étranger et ciblent le public suisse.

3 La présente section ne s’applique pas à la Société suisse de radiodiffusion et télévi-

sion (SSR).
```


### Replacement distractors

**row1344-X-1** - PDF/printed p.18; offsets [4, 568).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/PCWaDg8-GOcJ/2022-05-15_explications_du_conseil_federal.pdf)

PDF SHA-256: `f9c5d7830a90b9af3b0c8fde853e036a14ca1b111958342bb39ad98576adc308`.

Speaker: Federal Council and Parliament. Proposal: Loi sur le cinema.

Classification: `irrelevant`. Institutional approval does not determine the legal percentage; no 4 or 10 percent.

```text
Premier objet : loi sur le cinéma

Arguments

Conseil fédéral et Parlement
La modiﬁcation de la loi sur le cinéma comblera une lacune
créée par la transition numérique et remédiera à l’inégalité
de traitement entre les chaînes de télévision et les services
de streaming. L’extension de l’obligation d’investir aux services de streaming nationaux et internationaux contribuera
à promouvoir la production de ﬁlms suisses et à renforcer
la diversité culturelle de l’offre. Le Conseil fédéral et le Parlement approuvent le projet, notamment pour les raisons
suivantes.
```

**row1344-X-2** - PDF/printed p.29; offsets [43, 416).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/PCWaDg8-GOcJ/2022-05-15_explications_du_conseil_federal.pdf)

PDF SHA-256: `f9c5d7830a90b9af3b0c8fde853e036a14ca1b111958342bb39ad98576adc308`.

Speaker: Federal explanatory text / ballot text. Proposal: Organ transplantation Act.

Classification: `irrelevant`. Organ-donation communication, a different proposition.

```text
La population devra être informée du passage au modèle
du consentement présumé. C’est pourquoi la loi prévoit que des
informations complètes sur la nouvelle réglementation seront
fournies régulièrement. Ces informations devront parvenir à
tous les groupes de la population, y compris aux personnes
handicapées, et être conçues de façon à ce que tout le monde
les comprenne.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1422 | 469 | 701 | 701 | 232 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 1401: revised

Primary analysis: **retained**. Dataset gold remains `contradiction`. Claim language: `it`; source language: `it`.

Claim:

Secondo il testo di voto, l'Assemblea federale raccomanda al Popolo e ai Cantoni di approvare l'iniziativa.

Official nursing-initiative title p18 added before Assembly rejection p19. Dataset claim has a bare initiative; linkage follows recorded reference/proposal and remains a context assumption.

Speaker/proposal: Assemblea federale; Iniziativa sulle cure infermieristiche.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p28-c1 | 28; [0, 900) | `plausible_hard_negative` | replaced: Different justice-initiative legal text; clipped legal clause requires replacement. |
| p3-c1 | 3; [0, 469) | `irrelevant` | replaced: Contents listing; not a recommendation. |

### B / adjudication evidence

**row1401-B-1** - PDF/printed p.18; offsets [62, 228).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: Assemblea federale. Proposal: Iniziativa sulle cure infermieristiche.

```text
Il testo in votazione
Decreto federale
concernente l’iniziativa popolare «Per cure
infermieristiche forti (Iniziativa sulle cure infermieristiche)»
del 18 giugno 2021
```

**row1401-B-2** - PDF/printed p.19; offsets [1121, 1210).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: Assemblea federale. Proposal: Iniziativa sulle cure infermieristiche.

```text
Art. 2
L’Assemblea federale raccomanda al Popolo e ai Cantoni di respingere l’iniziativa.
```


### Replacement distractors

**row1401-X-1** - PDF/printed p.6; offsets [3, 492).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: Federal explanatory text / ballot text. Proposal: Justice initiative.

Classification: `plausible_hard_negative`. Different initiative explicitly named; no recommendation on nursing.

```text
Secondo oggetto: Iniziativa sulla giustizia

In breve

Iniziativa sulla giustizia

Contesto

Attualmente i giudici federali sono eletti, ogni sei anni,
dal Parlamento. Quest’ultimo bada a che le forze politiche
siano equamente rappresentate (rappresentanza proporzionale dei partiti). Per i promotori dell’iniziativa questa procedura
di elezione mina l’indipendenza dei giudici. Inoltre essi criticano il fatto che chi non è membro di un partito non ha alcuna
possibilità di essere eletto.
```

**row1401-X-2** - PDF/printed p.8; offsets [116, 950).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/TbPPMZBkuvPm/2021-11-28_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `72bc2e78fd62f8452a8fe9aebd31c5740e77d30e298ed940dcbf788b4ab8cba2`.

Speaker: Federal explanatory text / ballot text. Proposal: COVID-19 Act.

Classification: `irrelevant`. Pandemic legislative chronology, explicitly COVID-19, not nursing recommendation.

```text
La pandemia di COVID-19 ha costretto il Consiglio federale
a intervenire in modo rapido e capillare per proteggere le
persone e le imprese. Per questa ragione, all’inizio il Governo ha
dovuto in parte ricorrere al diritto di necessità. Dal settembre
2020, quando il Parlamento l'ha adottata, la legge COVID-19
dispone i provvedimenti aggiuntivi che il Consiglio federale
deve attuare per far fronte alla pandemia e limitare i danni
economici. In risposta all’evoluzione della crisi, la legge è stata
modiﬁcata più volte. A seguito di un referendum, il 13 giugno
2021 il Popolo ha approvato la legge con il 60 per cento dei
voti. Il 28 novembre una parte della legge sarà sottoposta
di nuovo al voto del Popolo, essendo stato chiesto un altro
referendum. Si tratta nello speciﬁco degli adeguamenti decisi
dal Parlamento nel marzo 2021.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1082 | 336 | 701 | 701 | 365 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 1475: revised

Primary analysis: **retained**. Dataset gold remains `contradiction`. Claim language: `it`; source language: `fr`.

Claim:

Secondo il testo sottoposto a votazione, l’Assemblea federale raccomanda al popolo e ai cantoni di approvare l’iniziativa.

Official arms-financing title p30 added before Assembly rejection p31. Dataset claim has a bare initiative; linkage follows recorded reference/proposal and remains a context assumption. Corroborating p7 Council rejection replaced with committee endorsement.

Speaker/proposal: Assemblee federale; Interdiction du financement des producteurs de materiel de guerre.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p7-c1 | 7; [0, 900) | `corroborating` | replaced: Council/Parliament rejection corroborates Federal Assembly rejection. |
| p18-c1 | 18; [0, 900) | `irrelevant` | replaced: Different responsible-businesses proposal. |

### B / adjudication evidence

**row1475-B-1** - PDF/printed p.30; offsets [53, 217).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/ywovGJwC1GeO/2020-11-29_explications_du_conseil_federal.pdf)

PDF SHA-256: `62870b79f34f5d9af48ca53709090140403133edc23ef393bf7b17bcdd35c48f`.

Speaker: Assemblee federale. Proposal: Interdiction du financement des producteurs de materiel de guerre.

```text
Texte soumis au vote
Arrêté fédéral concernant
l’initiative populaire « Pour une interdiction
du financement des producteurs de matériel de guerre »
du 19 juin 2020
```

**row1475-B-2** - PDF/printed p.31; offsets [1056, 1144).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/ywovGJwC1GeO/2020-11-29_explications_du_conseil_federal.pdf)

PDF SHA-256: `62870b79f34f5d9af48ca53709090140403133edc23ef393bf7b17bcdd35c48f`.

Speaker: Assemblee federale. Proposal: Interdiction du financement des producteurs de materiel de guerre.

```text
Art. 2
L’Assemblée fédérale recommande au peuple et aux cantons de rejeter l’initiative.
```


### Replacement distractors

**row1475-X-1** - PDF/printed p.7; offsets [606, 958).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/ywovGJwC1GeO/2020-11-29_explications_du_conseil_federal.pdf)

PDF SHA-256: `62870b79f34f5d9af48ca53709090140403133edc23ef393bf7b17bcdd35c48f`.

Speaker: Initiative committee. Proposal: Interdiction du financement des producteurs de materiel de guerre.

Classification: `plausible_hard_negative`. Initiative committee endorses financing ban; different speaker from Federal Assembly.

```text
Recommandation
du comité
d’initiative

Oui
Les armes peuvent faire beaucoup de mal. Le comité
estime donc qu’il est contraire à l’éthique que l’argent des
institutions financières suisses soit affecté à leur production.
Les caisses de pension pourraient aussi obtenir des rendements
à la hauteur du marché sans investir dans des entreprises
d’armement.
```

**row1475-X-2** - PDF/printed p.9; offsets [13, 977).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/ywovGJwC1GeO/2020-11-29_explications_du_conseil_federal.pdf)

PDF SHA-256: `62870b79f34f5d9af48ca53709090140403133edc23ef393bf7b17bcdd35c48f`.

Speaker: Federal explanatory text / ballot text. Proposal: Responsible businesses initiative.

Classification: `irrelevant`. Responsible-businesses initiative background; different proposition and no arms-financing recommendation.

```text
Ces dernières années, le débat portant sur la responsabilité des entreprises actives sur le plan international en matière
de droits de l’homme et de protection de l’environnement s’est
intensifié dans le monde entier. La Suisse participe à cette
discussion, a pris part à l’élaboration de normes uniformes au
niveau international et attend des entreprises suisses qu’elles
respectent ces normes également à l’étranger. Elle a en outre
élaboré deux plans d’action nationaux et institué un organe de
conciliation. Pour les auteurs de l’initiative, ces mesures ne vont
cependant pas assez loin. Ils demandent des règles plus
contraignantes et veulent que les entreprises suisses répondent
désormais également des dommages qui sont causés par des
entreprises qu’elles contrôlent. C’est pourquoi ils ont déposé
en octobre 2016 l’initiative « Entreprises responsables – pour
protéger l’être humain et l’environnement » (initiative pour
des multinationales responsables).
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 916 | 324 | 631 | 631 | 307 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 1: revised

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `de`; source language: `fr`.

Claim:

Bei Annahme der Abstimmung wird das Rentenalter ab 2033 automatisch an die Lebenserwartung gebunden und bei einem Anstieg der Lebenserwartung um 80 % der zusätzlichen Lebenszeit angehoben.

Post-2033 automatic 80-percent linkage retained together with two-month annual cap and five-year notice; source also explains implementation mechanics.

Speaker/proposal: Initiative description; Initiative sur les rentes.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p24-c2 | 24; [900, 1637) | `irrelevant` | replaced: Disability-insurance costs do not state 80-percent linkage. |
| p27-c1 | 27; [0, 900) | `irrelevant` | replaced: International comparison does not state linkage; clipped web address. |

### B / adjudication evidence

**row1-B-1** - PDF/printed p.22; offsets [4, 949).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/In9i5Kp4p64r/2024-03-03_explications_du_conseil_federal.pdf)

PDF SHA-256: `b28e64fbbdb39c3e9499056e433cbcb763c154799fff775262d0becd86d77cd9`.

Speaker: Initiative description. Proposal: Initiative sur les rentes.

```text
Deuxième objet : initiative sur les rentes

Lier l’âge de la
retraite à l’espérance
de vie

Après 2033, l’âge de la retraite augmentera automa­
tiquement en même temps que l’espérance de vie moyenne.
Cependant, il n’augmentera pas à l’identique, mais à raison
de 80 % de la durée de vie supplémentaire. D’un point de vue
purement mathématique, on peut dire que si l’espérance
de vie augmente d’un mois, l’âge de la retraite sera relevé
de 0,8 mois. Le Conseil fédéral et le Parlement devront définir
comment fonctionne cet automatisme dans le cadre de
la mise en œuvre de la nouvelle disposition constitutionnelle.

Deux mois par
an au maximum

À partir de 2033, l’âge de la retraite ne pourra pas
augmenter de plus de 2 mois par année, même si l’augmentation de l’espérance de vie devait justifier un relèvement plus
important. Tout relèvement devra être annoncé aux personnes
concernées cinq ans avant qu’elles atteignent l’âge de
la retraite.
```


### Replacement distractors

**row1-X-1** - PDF/printed p.24; offsets [905, 1080).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/In9i5Kp4p64r/2024-03-03_explications_du_conseil_federal.pdf)

PDF SHA-256: `b28e64fbbdb39c3e9499056e433cbcb763c154799fff775262d0becd86d77cd9`.

Speaker: Federal explanatory text / ballot text. Proposal: Initiative sur les rentes.

Classification: `irrelevant`. Disability-insurance spending consequence does not entail the 80-percent rule.

```text
L’initiative aura aussi des conséquences sur l’assuranceinvalidité. Les bénéficiaires d’une rente AI perçoivent une rente
AVS dès lors qu’ils ont atteint l’âge de la retraite.
```

**row1-X-2** - PDF/printed p.27; offsets [58, 433).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/In9i5Kp4p64r/2024-03-03_explications_du_conseil_federal.pdf)

PDF SHA-256: `b28e64fbbdb39c3e9499056e433cbcb763c154799fff775262d0becd86d77cd9`.

Speaker: Federal explanatory text / ballot text. Proposal: Initiative sur les rentes.

Classification: `irrelevant`. International comparison and age 66 do not establish automatic 80-percent linkage.

```text
L’initiative est modérée, surtout en comparaison internationale. Le Danemark, les Pays-Bas, la Belgique, l’Allemagne
et bien d’autres pays ont décidé de relever l’âge de la retraite
à 67 ans, voire plus, dans les dix prochaines années. L’initiative
prévoit de ne relever l’âge de la retraite en Suisse qu’à 66 ans
d’ici 2033, ce qui en fait une initiative modérée et sociale.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1464 | 518 | 671 | 671 | 153 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 550: excluded

Primary analysis: **excluded**. Dataset gold remains `neutral`. Claim language: `de`; source language: `fr`.

Claim:

Dem Abstimmungstext zufolge würde die Einführung eines gesetzlichen Mindestlohns von 40 Franken pro Stunde die Arbeitslosigkeit in der Schweiz erheblich verringern.

Excluded: stamp-duty excerpt cannot establish booklet-wide absence of CHF40 minimum-wage claim. Original neutral dataset label unchanged. No operational-control inference planned.

Speaker/proposal: Ballot question and opposing summaries; Modification de la loi federale sur les droits de timbre.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p32-c1 | 32; [0, 900) | `irrelevant` | excluded_with_case: Tobacco advertising; cannot prove minimum-wage absence. |
| p53-c1 | 53; [0, 900) | `irrelevant` | excluded_with_case: Media subsidy dispute; cannot prove minimum-wage absence. |

### B / adjudication evidence

**row550-B-1** - PDF/printed p.9; offsets [86, 444).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/JwKnnvQMcYT2/2022-02-13_explications_du_conseil_federal.pdf)

PDF SHA-256: `2d8cb9710acf095b5bdb2f5cf431f1bdd93e21b5e250b168170a1e249b0b7a22`.

Speaker: Ballot question and opposing summaries. Proposal: Modification de la loi federale sur les droits de timbre.

```text
Acceptez-vous la modiﬁcation
du 18 juin 2021 de la loi fédérale
sur les droits de timbre (LT) ?

Oui
Le Conseil fédéral et le Parlement veulent supprimer le
droit de timbre d’émission. Sa suppression aura un effet positif
sur l’attrait de la place économique suisse : elle générera de la
croissance, créera des emplois et permettra de préserver ces
derniers.
```


### Replacement distractors

No C/D evidence or inference planned for this excluded case.

## Row 1035: revised

Primary analysis: **retained**. Dataset gold remains `contradiction`. Claim language: `de`; source language: `fr`.

Claim:

Der Bundesrat rät zur Ablehnung der Vorlage, weil die vorhandenen Strassen genügen und keine weiteren Projekte erforderlich sind.

B now includes explicit institutional recommendation, ballot identity, Oui and six-project need. Corroborating p14 distractor replaced.

Speaker/proposal: Conseil federal et Parlement; Amenagement 2023 des routes nationales.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p18-c1 | 18; [0, 900) | `plausible_hard_negative` | replaced: Referendum committee opposing argument with explicit attribution. |
| p14-c1 | 14; [0, 816) | `corroborating` | replaced: Six projects and bottleneck need independently corroborate B. |

### B / adjudication evidence

**row1035-B-1** - PDF/printed p.5; offsets [35, 597).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/wHXT9BH3VlYQ/2024-11-24_explications_du_conseil_federal.pdf)

PDF SHA-256: `39d395833d051d950d37c75003b4ecbea917e221db17eed55e3cb5ffdcd364b1`.

Speaker: Conseil federal et Parlement. Proposal: Amenagement 2023 des routes nationales.

```text
Recommandation
du Conseil fédéral
et du Parlement

Acceptez-vous l’arrêté fédéral du
29 septembre 2023 sur l’étape d’aménagement 2023 des routes nationales ?

Oui
Les routes nationales sont surchargées en divers endroits
et le trafic continue d’augmenter, ce qui se traduit par des
embouteillages et des coûts élevés pour la population et l’économie. Le Conseil fédéral et le Parlement veulent éliminer
les goulets d’étranglement grâce à six projets ciblés, afin que
les camions et les voitures ne se rabattent pas sur les villages
et les quartiers d’habitation.
```


### Replacement distractors

**row1035-X-1** - PDF/printed p.18; offsets [4, 575).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/wHXT9BH3VlYQ/2024-11-24_explications_du_conseil_federal.pdf)

PDF SHA-256: `39d395833d051d950d37c75003b4ecbea917e221db17eed55e3cb5ffdcd364b1`.

Speaker: Referendum committee. Proposal: Amenagement 2023 des routes nationales.

Classification: `plausible_hard_negative`. Attributed referendum committee opposes extension, not Council recommendation.

```text
Premier objet : aménagement des routes nationales

Arguments

Comité référendaire
L’extension prévue des autoroutes est démesurée, en décalage
avec notre époque et excessivement coûteuse. Elle ne résoudra pas les problèmes : l’expérience et les études menées
montrent qu’une telle mesure engendre plus de trafic, d’embouteillages, de pollution atmosphérique, de bruit et d’émissions de CO2. Il nous faut une planification des transports
réfléchie et durable. C’est pourquoi une alliance d’environ
50 organisations soutient le référendum contre l’extension
des autoroutes.
```

**row1035-X-2** - PDF/printed p.28; offsets [1131, 1513).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/wHXT9BH3VlYQ/2024-11-24_explications_du_conseil_federal.pdf)

PDF SHA-256: `39d395833d051d950d37c75003b4ecbea917e221db17eed55e3cb5ffdcd364b1`.

Speaker: Federal explanatory text / ballot text. Proposal: Subletting law.

Classification: `irrelevant`. Subletting law, not national roads.

```text
Les restrictions à la sous-location ne font que créer
des obstacles inutiles. Aujourd’hui déjà, la sous-location n’est
possible qu’avec l’accord du bailleur, et le loyer perçu ne doit
pas être exagéré. Les risques d’abus sont donc minimes et les
cas restent rares. Le projet réduira fortement le droit à la
sous-location et les bailleurs pourront très facilement opposer
leur refus.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1126 | 392 | 637 | 637 | 245 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 189: revised

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `fr`; source language: `it`.

Claim:

Le Conseil fédéral préconise de rejeter l’initiative populaire « Pour une immigration modérée (Initiative de limitation) ».

B now contains immigration-limitation identity and Council/Parliament No. Initiative committee Si remains a legitimate attribution hard negative.

Speaker/proposal: Consiglio federale e Parlamento; Iniziativa per la limitazione.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p21-c2 | 21; [900, 1175) | `plausible_hard_negative` | replaced: Initiative committee Yes with explicit attribution. |
| p14-c1 | 14; [0, 273) | `irrelevant` | replaced: Title and contents only. |

### B / adjudication evidence

**row189-B-1** - PDF/printed p.5; offsets [38, 532).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/XuiMCko39BzI/2020-09-27_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `76acc2e7d58639dccae9d52d7cdeba73418f57aec9928fa0898017f7be2e5111`.

Speaker: Consiglio federale e Parlamento. Proposal: Iniziativa per la limitazione.

```text
Raccomandazione
del Consiglio
federale e del
Parlamento

Volete accettare l’iniziativa popolare
«Per un’immigrazione moderata
(Iniziativa per la limitazione)»?

No
Il Consiglio federale e il Parlamento respingono l’iniziativa poiché compromette la via bilaterale con l’UE. Essa mette a
repentaglio la stabilità delle relazioni con il principale partner
della Svizzera, minacciando così i posti di lavoro e la prosperità
in un periodo già caratterizzato da grande incertezza sul piano
economico.
```


### Replacement distractors

**row189-X-1** - PDF/printed p.21; offsets [880, 999).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/XuiMCko39BzI/2020-09-27_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `76acc2e7d58639dccae9d52d7cdeba73418f57aec9928fa0898017f7be2e5111`.

Speaker: Initiative committee. Proposal: Iniziativa per la limitazione.

Classification: `plausible_hard_negative`. Explicit initiative-committee Yes is not the Council position.

```text
Raccomandazione
del comitato
d’iniziativa

Per tutte queste ragioni, il comitato d’iniziativa raccomanda di votare:

Sì
```

**row189-X-2** - PDF/printed p.15; offsets [50, 492).

[Official PDF](https://www.bk.admin.ch/dam/it/sd-web/XuiMCko39BzI/2020-09-27_spiegazioni_del_consigliofederale.pdf)

PDF SHA-256: `76acc2e7d58639dccae9d52d7cdeba73418f57aec9928fa0898017f7be2e5111`.

Speaker: Federal explanatory text / ballot text. Proposal: Iniziativa per la limitazione.

Classification: `irrelevant`. Current admission policy, no initiative recommendation.

```text
La politica di immigrazione della Svizzera distingue tra due
gruppi di Paesi. I cittadini degli Stati membri dell’Unione europea
(UE) e dell’Associazione europea di libero scambio (AELS)1 bene ﬁciano della libera circolazione delle persone. I cittadini di tutti
gli altri Stati sottostanno invece a criteri di ammissione più severi;
per l’accesso al mercato del lavoro, inoltre, il Consiglio federale
stabilisce ogni anno contingenti massimi.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1212 | 379 | 543 | 543 | 164 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 195: revised

Primary analysis: **retained**. Dataset gold remains `entailment`. Claim language: `fr`; source language: `fr`.

Claim:

Le comité estime que les dispositions actuelles du code pénal suffisent déjà à punir les insultes et l’humiliation publique d’une personne, de sorte qu’une nouvelle loi contre la discrimination n’est pas nécessaire.

Disputed v1 entailment resolved with stronger source: p7 committee explicitly says insults or public belittling already punished and new law unnecessary; p22 lists existing Penal Code protection. Supports the committee opinion, not objective legal sufficiency.

Speaker/proposal: Comite referendaire; Interdiction de la discrimination en raison de l’orientation sexuelle.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p24-c1 | 24; [0, 900) | `plausible_hard_negative` | replaced: Institutional protection assessment, different speaker. |
| p7-c1 | 7; [0, 900) | `ambiguous_or_decisive` | replaced: v1 excerpt clips committee argument; completing coherent paragraph yields decisive p7 evidence, now used in B. |

### B / adjudication evidence

**row195-B-1** - PDF/printed p.7; offsets [669, 1035).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/aSmZ7rOvZDrG/2020-02-09_explications_du_conseil_federal.pdf)

PDF SHA-256: `e57074725ce371592bfb0760665c3d90d99b972ca48dfcb0577022276da9a54e`.

Speaker: Comite referendaire. Proposal: Interdiction de la discrimination en raison de l’orientation sexuelle.

```text
Recommandation
du comité
référendaire

Non
Selon le comité, on nous vend comme norme anti-discrimination une loi qui impose en réalité une censure. Cette
loi menace la liberté d’opinion et de conscience et la liberté
de commerce. En outre elle est inutile : quiconque insulte
ou rabaisse publiquement une personne est en effet déjà
sanctionné pénalement aujourd’hui.
```

**row195-B-2** - PDF/printed p.22; offsets [1565, 1874).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/aSmZ7rOvZDrG/2020-02-09_explications_du_conseil_federal.pdf)

PDF SHA-256: `e57074725ce371592bfb0760665c3d90d99b972ca48dfcb0577022276da9a54e`.

Speaker: Comite referendaire. Proposal: Interdiction de la discrimination en raison de l’orientation sexuelle.

```text
Le code pénal (art. 173 ss CP) contient des bases légales
solides qui permettent déjà de se défendre en cas d’atteinte à
l’honneur, d’injure, de menace, de diffamation ou de calomnie.
Il est parfaitement inutile et contre-productif de faire une
nouvelle loi anti-discrimination qui ne protège qu’en apparence.
```


### Replacement distractors

**row195-X-1** - PDF/printed p.24; offsets [4, 575).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/aSmZ7rOvZDrG/2020-02-09_explications_du_conseil_federal.pdf)

PDF SHA-256: `e57074725ce371592bfb0760665c3d90d99b972ca48dfcb0577022276da9a54e`.

Speaker: Federal Council and Parliament. Proposal: Interdiction de la discrimination en raison de l’orientation sexuelle.

Classification: `plausible_hard_negative`. Council/Parliament consider protection insufficient; different speaker from committee.

```text
Deuxième objet : interdiction de la discrimination

Arguments

Conseil fédéral et Parlement
Pour le Parlement, la protection contre la discrimination en
raison de l’orientation sexuelle est insuffisante. La modification du code pénal vise à renforcer cette protection. La liberté
d’expression ne sera pas compromise puisque les débats
d’opinion resteront possibles. Seul sera interdit le fait d’abaisser publiquement des personnes en raison de leur orientation
sexuelle. Le Conseil fédéral et le Parlement approuvent le
projet, en particulier pour les raisons suivantes :
```

**row195-X-2** - PDF/printed p.20; offsets [67, 243).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/aSmZ7rOvZDrG/2020-02-09_explications_du_conseil_federal.pdf)

PDF SHA-256: `e57074725ce371592bfb0760665c3d90d99b972ca48dfcb0577022276da9a54e`.

Speaker: Federal explanatory text / ballot text. Proposal: Interdiction de la discrimination en raison de l’orientation sexuelle.

Classification: `irrelevant`. Intent requirement does not establish the committee claim about existing protection.

```text
Un comportement discriminatoire n’est punissable que s’il
y a intention, c’est-à-dire si l’auteur agit délibérément ou
même précisément dans le dessein de blesser une personne.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1265 | 435 | 603 | 603 | 168 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

## Row 1058: revised

Primary analysis: **retained**. Dataset gold remains `contradiction`. Claim language: `de`; source language: `fr`.

Claim:

Laut der Zusammenfassung gilt die Abschaffung der Vermietungswertbesteuerung nur für Zweitwohnungen, nicht für Hauptwohnungen.

Both primary and secondary residences explicitly included in abolition. Added distinct constitutional special tax to prevent conflation; hard negatives preserve the separate measure/minority speaker.

Speaker/proposal: En bref summary; Impot immobilier cantonal sur les residences secondaires.

### Original distractor audit

| Original ID | Page; offsets | Classification | Disposition/reason |
|---|---|---|---|
| p19-c1 | 19; [0, 840) | `plausible_hard_negative` | replaced: Special secondary-residence tax is separate from abolition. |
| p5-c1 | 5; [0, 900) | `ambiguous_or_decisive` | replaced: Clipped minority/adopted-policy comparison invites scope confusion. |

### B / adjudication evidence

**row1058-B-1** - PDF/printed p.4; offsets [3, 44).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/6DaWglL-N7NM/2025-09-28_explications_du_conseil_federal.pdf)

PDF SHA-256: `f426e4637a10ecdb7a14296c6455918d47e90b4347a953156be1c00cf1bbfd67`.

Speaker: En bref summary. Proposal: Impot immobilier cantonal sur les residences secondaires.

```text
Premier objet : impôt immobilier

En bref
```

**row1058-B-2** - PDF/printed p.4; offsets [350, 728).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/6DaWglL-N7NM/2025-09-28_explications_du_conseil_federal.pdf)

PDF SHA-256: `f426e4637a10ecdb7a14296c6455918d47e90b4347a953156be1c00cf1bbfd67`.

Speaker: En bref summary. Proposal: Impot immobilier cantonal sur les residences secondaires.

```text
Le Parlement a décidé de modifier la loi
pour abolir l’imposition de la valeur locative et limiter les
déductions fiscales. La modification vaut pour les résidences
tant principales que secondaires. Il a aussi décidé de modifier
la Constitution pour que les cantons puissent percevoir un
impôt immobilier spécial sur les résidences secondaires essentiellement à usage personnel.
```


### Replacement distractors

**row1058-X-1** - PDF/printed p.19; offsets [40, 358).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/6DaWglL-N7NM/2025-09-28_explications_du_conseil_federal.pdf)

PDF SHA-256: `f426e4637a10ecdb7a14296c6455918d47e90b4347a953156be1c00cf1bbfd67`.

Speaker: Federal Council and Parliament. Proposal: Impot immobilier cantonal sur les residences secondaires.

Classification: `plausible_hard_negative`. Distinct special tax applies to secondary homes, not scope of abolished imputed-value tax.

```text
Il est important de pouvoir percevoir un impôt immobilier
spécial sur les résidences secondaires essentiellement à usage
personnel. Cette possibilité donne aux cantons et aux communes à forte densité de résidences secondaires la marge de
manœuvre nécessaire pour compenser les éventuelles baisses
de recettes fiscales.
```

**row1058-X-2** - PDF/printed p.5; offsets [496, 874).

[Official PDF](https://www.bk.admin.ch/dam/fr/sd-web/6DaWglL-N7NM/2025-09-28_explications_du_conseil_federal.pdf)

PDF SHA-256: `f426e4637a10ecdb7a14296c6455918d47e90b4347a953156be1c00cf1bbfd67`.

Speaker: Minority of Parliament. Proposal: Impot immobilier cantonal sur les residences secondaires.

Classification: `plausible_hard_negative`. Explicit minority preference to retain tax is not the adopted abolition scope.

```text
Position
de la minorité
du Parlement

Non
Une minorité du Parlement rejette la réforme. Une partie
veut conserver l’imposition de la valeur locative au motif que
l’abolition profite surtout aux propriétaires de leur logement
et qu’elle peut conduire à une baisse des recettes fiscales de
l’État. Une autre partie veut garder au moins l’imposition sur
les résidences secondaires.
```

### Frozen offline token counts

| A | B | C | D | C minus B | D minus C |
|---:|---:|---:|---:|---:|---:|
| 1377 | 339 | 500 | 500 | 161 | 0 |

B/C is length-confounded. C/D preserves the wording, page headers, passage metadata, model settings, completion/context budgets and both internal block orders.

