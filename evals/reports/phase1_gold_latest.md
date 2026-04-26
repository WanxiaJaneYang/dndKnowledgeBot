# Phase 1 Gold-Set Eval — phase1_gold_v1

- **Run started:** 2026-04-26T05:25:26Z
- **Cases:** 30
- **Behavior match rate:** 0.47

## Tag counts

| tag | count |
|---|---|
| `retrieval_miss` | 0 |
| `wrong_section` | 9 |
| `wrong_entry` | 0 |
| `citation_mismatch` | 1 |
| `unsupported_inference` | 0 |
| `missing_abstain` | 1 |
| `unnecessary_abstain` | 15 |
| `edition_boundary_failure` | 0 |
| `_clean` | 5 |

## Failing cases

### Tag: `wrong_section`

#### P1-DL-001 — direct_lookup → direct_answer

**Question:** When does a character provoke an attack of opportunity from movement?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> Sometimes a combatant in a melee lets her guard down. In this case, combatants near her can take advantage of her lapse in defense to attack her for free. These free attacks are called attacks of…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | CombatI > ATTACKS OF OPPORTUNITY | yes | no | no | ['attack', 'opportunity'] |

#### P1-EX-001 — exception_lookup → direct_answer

**Question:** Does drinking a potion provoke an attack of opportunity?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> A potion is a magic liquid that produces its effect when imbibed. Magic oils are similar to potions, except that oils are applied externally rather than imbibed. A potion or oil can be used only…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | MagicItemsIII > POTIONS AND OILS | yes | no | no | ['potion'] |

#### P1-EX-002 — exception_lookup → direct_answer

**Question:** Can you make attacks of opportunity while flat-footed?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> Benefit: You may make a number of additional attacks of opportunity equal to your Dexterity bonus. With this feat, you may also make attacks of opportunity while flat-footed. Normal: A character…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | Feats > COMBAT REFLEXES [GENERAL] | yes | no | no | ['attacks', 'flat', 'footed', 'make', 'opportunity', 'while'] |

#### P1-EX-003 — exception_lookup → direct_answer

**Question:** Does firing a ranged weapon while threatened provoke an attack of opportunity?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> Sometimes a combatant in a melee lets her guard down. In this case, combatants near her can take advantage of her lapse in defense to attack her for free. These free attacks are called attacks of…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | CombatI > ATTACKS OF OPPORTUNITY | yes | no | no | ['attack', 'opportunity', 'threatened', 'while'] |

#### P1-EX-005 — exception_lookup → supported_inference

**Question:** Can a helpless target make attacks of opportunity?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> A helpless opponent is someone who is bound, sleeping, paralyzed, unconscious, or otherwise at your mercy. Regular Attack: A helpless character takes a -4 penalty to AC against melee attacks, but no…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | CombatII > HELPLESS DEFENDERS | yes | no | yes | ['attacks', 'helpless'] |

#### P1-MC-005 — direct_lookup → direct_answer

**Question:** Can you charge through difficult terrain?

**Tags:** `wrong_section`, `citation_mismatch`

**Actual:** grounded · primary support: direct_support
> Diagonals: When measuring distance, the first diagonal counts as 1 square, the second counts as 2 squares, the third counts as 1, the fourth as 2, and so on. You can't move diagonally past a corner…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | CombatII > Measuring Distance | yes | no | no | [] |

#### P1-TB-002 — table_dependent → direct_answer

**Question:** What ability modifier does an ability score of 18 provide?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> The ability that your powers depend on--your key ability score as a manifester--is related to what psionic class (or classes) you have levels in: Intelligence (psion), Wisdom (psychic warrior), and…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | PsionicClasses > ABILITIES AND MANIFESTERS | yes | no | no | ['ability', 'modifier', 'score'] |

#### P1-TB-003 — table_dependent → direct_answer

**Question:** What is the armor check penalty for full plate?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> The following specific suits of armor usually are preconstructed with exactly the qualities described here. Adamantine Breastplate: This nonmagical breastplate is made of adamantine, giving its…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | MagicItemsII > Specific Armors | yes | no | no | ['armor'] |

#### P1-TB-005 — table_dependent → direct_answer

**Question:** What size modifier applies to attack rolls for a Large creature?

**Tags:** `wrong_section`

**Actual:** grounded · primary support: direct_support
> Your attack bonus with a melee weapon is: Base attack bonus + Strength modifier + size modifier With a ranged weapon, your attack bonus is: Base attack bonus + Dexterity modifier + size modifier +…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | CombatI > ATTACK BONUS | yes | no | no | ['attack', 'large', 'modifier', 'size'] |
| cit_2 | srd_35 · 3.5e | CombatII > Grapple Checks | yes | no | no | ['attack', 'large', 'modifier', 'size'] |

### Tag: `missing_abstain`

#### P1-IE-003 — insufficient_evidence → abstain

**Question:** Can I spend inspiration to gain advantage on an attack roll?

**Tags:** `missing_abstain`

**Actual:** grounded · primary support: direct_support
> You project a field of improbability around yourself, creating a fleeting protective shell. You gain a +4 deflection bonus to Armor Class. You can manifest this power instantly, quickly enough to…

**Citations:**

| id | source · edition | section_path | source | section | entry | tokens shared |
|----|-----|-----|---|---|---|---|
| cit_1 | srd_35 · 3.5e | PsionicPowersG-P > Power Points: 5 | no | n/a | n/a | ['attack', 'gain'] |

### Tag: `unnecessary_abstain`

#### P1-DL-002 — direct_lookup → direct_answer

**Question:** What does the total defense action do to Armor Class?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-DL-003 — direct_lookup → direct_answer

**Question:** What is the default speed for a human in combat movement terms?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-DL-004 — direct_lookup → direct_answer

**Question:** Can a character take a 5-foot step if they did any other movement in the same round?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-DL-005 — direct_lookup → direct_answer

**Question:** What does being dazzled do?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-EX-004 — exception_lookup → direct_answer

**Question:** Can you run in heavy armor?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-NE-001 — named_entry → direct_answer

**Question:** What does the Power Attack feat allow you to trade?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-NE-002 — named_entry → direct_answer

**Question:** Without the Two-Weapon Fighting feat and with a non-light off-hand weapon, what are the two-weapon attack penalties?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-NE-003 — named_entry → direct_answer

**Question:** How does the Dodge feat work?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-NE-004 — named_entry → direct_answer

**Question:** What does Magic Missile do on a hit roll?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-NE-005 — named_entry → direct_answer

**Question:** What does the Cleave feat trigger on?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-MC-002 — multi_chunk → supported_inference

**Question:** If a character is invisible and attacks, what combat advantages apply to that first attack?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-MC-003 — direct_lookup → direct_answer

**Question:** Can you cast defensively while threatened, and what check determines success?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-MC-004 — multi_chunk → supported_inference

**Question:** If you use Tumble to move through threatened squares, what does it prevent and what does it not prevent?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-TB-001 — table_dependent → direct_answer

**Question:** What Strength score carrying capacity applies to a medium load for Strength 10?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


#### P1-TB-004 — direct_lookup → direct_answer

**Question:** What cover bonus does improved cover grant?

**Tags:** `unnecessary_abstain`

**Actual:** abstain · primary support: n/a
> _abstain: Insufficient evidence: retrieved chunks do not clearly match the query._


## Clean tail

_5 clean cases (P1-MC-001, P1-IE-001, P1-IE-002, P1-IE-004, P1-IE-005)_
