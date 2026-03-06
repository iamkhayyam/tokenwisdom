---
title: "The Race That Eats Its Own Rules"
slug: the-race-that-eats-its-own-rules
id: 69af41ff408a6400011c9381
published_at: 2026-03-06T15:19:00.000-08:00
updated_at: 2026-03-09T16:36:23.000-07:00
featured: False
reading_time: 12 min
feature_image: https://tokenwisdom.ghost.io/content/images/2026/03/a-new-yorker-style-gouache-illustration-__T1HroJiRImXmq6XCxKw0g_EKJeR5TtSyuqorExo7UQNw_cover_sd.jpeg
excerpt: "W10 - The infrastructure of good intentions has quietly become the infrastructure of acceleration. Not corruption. Rational adaptation. Seven researchers warned about this in 1945. The people who built this understand it best — and they're all outside the institutions now.
"
url: https://tokenwisdom.ghost.io/the-race-that-eats-its-own-rules/
tags:
  - name: A.I. (and Subsets)
    slug: ai
  - name: Big Tech
    slug: big-tech
  - name: ANI \ AGI \ ASI
    slug: agi
  - name: Ethics \ Principles
    slug: ethical
  - name: Risk \ Reward
    slug: risk-reward
  - name: OpenAI + e/acc
    slug: gpt
  - name: Failing Up \ Often
    slug: failing-up
  - name: Future of Work
    slug: future-of-work
  - name: Philosophical
    slug: philosophy
  - name: 👁️ A Closer Look
    slug: a-closer-look
authors:
  - name: 🌶️ @iamkhayyam 
    slug: iamkhayyam
---

# The Race That Eats Its Own Rules

W10 •A• The Race That Eats Its Own Rules ✨ - NotebookLM ➡ Token Wisdom ✨In this episode of The Deep Dig, we dissect a provocative piece of analysis titled “The Race That Eats Its Own Rules” — a forensic takedown of the AI…NotebookLM ➡ Token Wisdom ✨

"When you see something that is technically sweet, you go ahead and do it and you argue about what to do about it only after you have had your technical success."

— According to J. Robert Oppenheimer






A Pattern Recognition on the AI Model Wars

They knew. They said so. Then they shipped it anyway...

Every major technology company with access to large language model capability in 2022 looked at what they had and decided not to release it. Google. DeepMind. Meta. Organizations with more users, more capital, more distribution infrastructure than the one that eventually moved.

They all held back. One didn’t.

The story Silicon Valley tells about this moment is that Google was slow — bureaucratic, flat-footed, out-innovated by a scrappy upstart willing to move fast. Convenient story. Also constructed almost entirely by the people who benefited from it. The less flattering reading: the organizations that held back had thought through what it means to deploy a system that confabulates with confidence, and decided the exposure wasn’t worth it. Google’s entire business is a trust relationship built on factual retrieval. A system that invents citations with complete syntactic fluency is architecturally hostile to that trust. So they waited.

OpenAI didn’t have that relationship to protect. What they had was a funding model to justify, a valuation to defend, and a competitive window that would not stay open indefinitely. So they moved. And once they moved, the race logic consumed everyone else — including Google, which rushed Bard to market so visibly unready that it produced a factual error in its own launch demo and erased roughly $100 billion in Alphabet’s market cap in a single day.

That is not a story about innovation. That is a story about what happens to judgment when the race is real and the window is closing.


The Failure Mode with a Name

The industry chose the word hallucination. That choice deserves more scrutiny than it gets. Hallucination implies a temporary aberration — a mind that has slipped its moorings but will, presumably, find them again. It carries clinical distance. It points away from design and toward accident. It is, in other words, exactly the word you would choose if you needed a failure mode to sound like weather rather than a decision.

Here is what is mechanically happening. Large language models do not retrieve facts from indexed memory the way a database does. They generate statistically probable continuations of text based on patterns absorbed during training. When a model produces a false citation, a fabricated study, a confident wrong answer — it is not malfunctioning. It is doing exactly what it was designed to do: produce fluent, contextually plausible text.

The problem is that “contextually plausible” and “factually true” are entirely different properties, and the architecture does not distinguish between them. It cannot. That distinction is not a missing feature awaiting a patch. It is baked into the approach.

Research into reducing hallucination rates — retrieval-augmented generation, chain-of-thought prompting, grounding outputs against external knowledge bases — has produced real reductions in constrained domains. The rate is not fixed. But reducing it costs money, adds latency, narrows the product’s apparent capability, and slows deployment. Every one of those costs runs directly against the logic of the race.

So the companies made a choice: ship with higher hallucination rates than were achievable, call it a “limitation,” and communicate that limitation in language implying it was temporary and being actively fixed.

The instinct is to reach for a simple metaphor — a missing wheel, a broken part. That framing lets the industry off too easily, because a missing wheel is obvious. Nobody drives on three wheels by accident. This is closer to a speedometer calibrated to look accurate across most conditions but carrying a systematic measurement error you cannot predict in advance. Usually right. Occasionally, dramatically wrong. And it will get people killed precisely because they trust it — because nothing in the instrument’s presentation signals the moment it stops being reliable. That is not a defect. That is a confidence miscalibration problem embedded in the instrument itself, shipped to market with full knowledge of what it was.


The Ideological Betrayal That Wasn’t Surprising

OpenAI was founded in 2015 as a nonprofit with an explicit mission: ensure that artificial general intelligence benefits all of humanity. The “open” in the name was not decorative. The founding thesis — stated plainly, publicly, repeatedly — held that concentrated, secretive, commercially-driven AI development was specifically dangerous, and that the antidote was an organization structurally insulated from profit incentives.

Not “we want to be nice.”

“We exist to be the alternative to the thing that will get everyone killed.”

That was the pitch.

By 2019, they had a “capped profit” subsidiary to attract investment. By 2023, Microsoft was inside the structure — billions committed, products dependent, interests thoroughly entangled. Then came the GPT-4 technical report: published March 2023, pages long, almost entirely empty of the architecture details, training methodology, and data composition that would allow independent evaluation.

Read that again.

A company named OpenAI released a scientific paper specifically designed to prevent science from being done on it. The stated justification was competitive sensitivity and safety. The practical effect was that independent evaluation of the system’s failure modes became impossible. You cannot audit what you cannot see.

Then November 2023. The board — including Ilya Sutskever, the co-founder with the deepest technical understanding of what was actually being built — voted to remove Sam Altman. The documented concern involved Altman’s candor with the board on safety-related matters. Within days, under pressure from investors and employees whose equity was tied to Altman’s continued leadership, Sutskever reversed his vote publicly. Altman was reinstated. Sutskever eventually left entirely to found Safe Superintelligence — an organization that has committed to building nothing deployable until it can build something safe. Draw your own conclusions about what that exit communicates.

Geoffrey Hinton built the theoretical foundation this entire industry stands on. He left Google — not to retire, but to speak. The institution, he concluded, made honesty structurally impossible.

Yoshua Bengio, whose contributions sit at the same foundational level, didn’t leave his academic post. He’s spent an increasing share of his public presence warning about the thing he helped create.

When the architects of a technology dedicate their later careers to arguing it needs to be slowed down, that is data.

The people who built this and understand it most deeply are sounding the loudest alarms from outside the institutions. The institutions are accelerating.


Terrible Projects We’ve Done Before

None of this is new. That is the part nobody wants to say out loud, because if you admit the pattern is legible, you also have to admit you can see where it goes.

In June 1945, seven senior Manhattan Project scientists — including James Franck and Glenn Seaborg — produced what became known as the Franck Report. It explicitly recommended against dropping the bomb on a civilian target without prior demonstration, on the specific grounds that doing so would trigger a global arms race the United States could not ultimately win.

The recommendation was ignored. The race logic overrode it: the Soviet Union was advancing, the window was open, the weapon was ready. Four years later, the Soviets tested their first device.

The Franck Report had predicted this with uncomfortable precision, and nobody who ignored it ever fully accounted for that.

What followed was five decades of deterrence — a stability maintained not by wisdom or design but by the fact that no single miscalculation proved fatal. Historians who study the Cold War near-misses tend to come away quieter than when they started. The margin was not what the official record suggested.

The structure of what is happening now is identical. Small group develops a capability so consequential that possessing it confers enormous power. Group initially operates with idealistic framing: carefully, openly, for everyone’s benefit. Competitive signal arrives. Idealistic framing collapses, because the race logic is totalizing — if you don’t move, someone else does, and then you’ve lost both the power and any ability to shape how it gets used. So everyone moves. Safeguards get subordinated to deployment speed. The researchers who understand the risks most clearly either adapt or leave.

What makes this iteration more acute than the nuclear case is the absence of physical constraint. A nuclear weapon requires fissile material, specialized manufacturing, a footprint that satellites can monitor and intelligence services can track. A competitive AI model requires compute, data, and a download. The nonproliferation logic that eventually stabilized the nuclear situation — control the inputs, verify the inventories, negotiate the treaties — applies imperfectly at best to a technology that can be copied, modified, and redistributed at essentially zero marginal cost.

The infrastructure for managing nuclear risk took thirty years to build. It barely held. The equivalent for AI does not yet exist in any meaningful form and we are much earlier in the timeline than we think.


The Mechanism That Selects Against Caution

The race dynamic doesn’t just accelerate development. It actively selects against the people most qualified to slow it down. This is the part that tends to get missed in coverage that focuses on individual actors.

The November 2023 OpenAI board crisis is the cleanest illustration available. The economic infrastructure built around Altman’s leadership — hundreds of millions in employee equity, a multi-billion dollar Microsoft partnership, a valuation requiring continued momentum — made his removal functionally catastrophic for the company’s survival, independent of whether the board’s concerns were valid. Six hundred employees threatened to resign. The pressure was not ideological. It was structural.

The people with the most to lose from a safety-first posture had accumulated, through the normal mechanics of startup financing and equity compensation, enough leverage to reverse a board decision in days.

This is a system behaving exactly as designed. The race builds financial structures — valuations, investor commitments, competitive positioning, employee equity — that become, over time, more powerful than any individual’s stated principles. The safety-conscious either adapt their views to survive inside the institution or they leave. The ones who stay get described as “maturing.” The ones who leave get described as idealists who couldn’t handle the real world. Both framings do the same work: they make the outcome look inevitable rather than chosen.

Sam Altman did not start as a cynical actor. The evidence suggests he started as someone who genuinely believed what he was saying. What the record shows is a person with normal human responses to competitive pressure and financial incentive, operating inside a system that consistently rewarded moving faster and punished hesitation.

Open-source idealist. Nonprofit founder. Capped-profit executive. Full commercial operator. Government AI infrastructure partner.

That is not a story of corruption. It is a story of rational adaptation to an incentive structure that was always going to produce exactly this outcome. The trajectory was not a surprise to anyone paying attention.

Which means the problem cannot be solved by finding better people. The Franck Report scientists were better people — more technically informed, more genuinely concerned about long-term consequences — than the decision-makers who overruled them. It didn’t matter. Better founders, better boards, better stated commitments to safety will produce the same result inside the same structure, because the structure is what generates the result. The race is driving. The people are passengers who believe they’re steering.


What This Means

Strip away the product announcements, the benchmark comparisons, the congressional testimony, and what you have is this: race logic operating on rational actors inside a system that has not developed the institutional infrastructure to constrain it.

The hallucination problem is a symptom. The governance crisis is a symptom. The ideology-to-commercial pipeline is a symptom.

The disease is the race itself.

We know from documented historical precedent that this dynamic overrides safety considerations in high-stakes technology development. We know the people most qualified to pump the brakes are being systematically selected out of the institutions doing the development. We know the failure modes of current systems are not resolved and may not be resolvable within current architectural approaches without trade-offs the market will not reward.

And we know that the one person who broke the seal — who started the current race by deploying first — began as an open-source idealist, abandoned that framing when capital required it, and has since signed agreements with the US government that sit in direct opposition to the mission that justified his organization’s existence.

If he bends that easily under capital pressure, the inference about what happened to the safety evaluations is not paranoia. It is pattern recognition. Organizations that compromise on foundational principles tend to compromise on all of them — not because the people are bad, but because the race is real, the pressure is real, and the institutional constraints that might have held the line were dismantled one rationalization at a time, before anyone had to make a single explicitly dishonest decision.

You are not buying a product. You are buying the output of a race.

Key sources informing this essay:

🧾 Bard demo error / Alphabet market cap loss.

 * NPR, February 9, 2023: “Google’s AI chatbot, Bard, sparks a $100 billion loss in Alphabet shares.”
 * CNN Business, February 8, 2023: “Google shares lose $100 billion after company’s AI chatbot makes an error during demo.”

🧾 GPT-4 Technical Report / architecture withheld.
OpenAI (2023). “GPT-4 Technical Report.” arXiv:2303.08774. Direct quote from the report: “Given both the competitive landscape and the safety implications of large-scale models like GPT-4, this report contains no further details about the architecture (including model size), hardware, training compute, dataset construction, training method, or similar.”

🧾 OpenAI board crisis, November 2023.

 * Wikipedia: “Removal of Sam Altman from OpenAI” (sourced from Axios, The Verge, The Wall Street Journal, PBS NewsHour).
 * CNBC, November 20, 2023: “Hundreds of OpenAI employees threaten to follow Altman to Microsoft unless board resigns.”
 * ABC News, November 20, 2023: “Sam Altman hired by Microsoft, 600 OpenAI employees threaten to quit.”

Note on employee count: Reported figures vary across sources — ABC News and Wired reported approximately 600; CNN reported 505 initial signatories with the number rising; The Drum cited “around 600 of OpenAI’s 700 employees”; Wikipedia’s article (citing multiple outlets) states nearly all of the startup’s 770 employees. The text uses 600 as the most consistently cited figure at the time of the employee letter.

🧾 Sutskever departure and Safe Superintelligence.

 * CNBC, June 19, 2024: “OpenAI co-founder Ilya Sutskever announces Safe Superintelligence.”
 * SSI mission statement (ssi.inc): “SSI is our mission, our name, and our entire product roadmap… our business model means safety, security, and progress are all insulated from short-term commercial pressures.”

🧾 Geoffrey Hinton departure from Google.

 * CNN, May 1, 2023: “Geoffrey Hinton: AI pioneer quits Google to warn about the technology’s dangers.”
 * MIT Technology Review, May 2, 2023: “Geoffrey Hinton tells us why he’s now scared of the tech he helped build.” Direct quote from Hinton: “I want to talk about AI safety issues without having to worry about how it interacts with Google’s business. As long as I’m paid by Google, I can’t do that.”

🧾 Franck Report (June 11, 1945).

 * Primary source: U.S. National Archives, Record Group 77, Manhattan Engineer District, Harrison-Bundy File, folder #76. Full text available at https://www.dannen.com/decision/franck.html
 * Atomic Heritage Foundation summary
 * Wikipedia entry with citation history
 * Bulletin of the Atomic Scientists contextual history

Note on Franck Report signatories: The committee had seven members, not six as sometimes cited (Britannica’s entry on Seaborg says six; the National Archives version lists seven: James Franck (chair), Donald J. Hughes, J. J. Nickson, Eugene Rabinowitch, Glenn T. Seaborg, J. C. Stearns, and Leo Szilárd). The text refers to the report by its common attribution to Franck and Seaborg without specifying total signatory count.

🧾 OpenAI founding (2015) and capped-profit restructuring (2019).

 * The Drum, November 2023 (citing company history): “Founded as a nonprofit in 2015 by Altman, Sutskever, Brockman, Elon Musk and others with the express mission of creating safe artificial general intelligence (AGI) that maximizes human flourishing, the company switched to a ‘capped-profit’ model in 2019.”

Don't miss the weekly roundup of articles and videos from the week in the form of these Pearls of Wisdom. Click to listen in and learn about tomorrow, today.

W09 •B• Pearls of Wisdom - 149th Edition 🔮 Weekly Curated List - NotebookLM ➡ Token Wisdom ✨In this episode of The Deep Dig, hosts explore the 149th edition of Token Wisdom, themed around a single powerful concept: substrate — the underlying…NotebookLM ➡ Token Wisdom ✨

Sign up now to read the post and get access to the full library of posts for subscribers only.

149th Edition 🔮 Token Wisdom \ Week 09This week: A rogue AI published a hit piece, and thermodynamic tech rivals GPUs at lower energy. Britain aims to predict crimes, while Terence Tao sees AI reshaping math. We aren’t building intelligence; we’re industrializing prediction—surveillance with better branding.Token Wisdom ✨🌶️ iamkhayyam


About the Author

Khayyam Wakil carries the name of a mathematician whose most precise work was used for centuries without acknowledgment. He finds this pattern recurring everywhere he looks.

He has spent two decades building companies at the edges of what technology could do: immersive media, artificial intelligence, ternary computing. Then a problem he couldn't put down led him, at 2am in a silent Calgary winter, into the mathematics underneath everything else.

On November 22nd, 2025, he became a mathematician.

He is the founder of CacheCow Agriculture Inc. and The ARC Institute of Knowware, where the geometry hiding in numbers is being turned into things that matter. He has watched the AI race from inside the institutions that built it. The Franck Report was declassified in 1946. It took another four years for the Soviets to test their first device, and decades more before anyone seriously accounted for what had been ignored.

Token Wisdom is where he writes while the work is still warm.

Subscribe at https://tokenwisdom.ghost.io

#leadership #longread | 🧠⚡ | #tokenwisdom #thelessyouknow 🌈✨



