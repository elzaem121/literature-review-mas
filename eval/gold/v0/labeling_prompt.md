# Labeling prompts

One system prompt per topic, rendered from the topic configs.

## t1_social_media

You label one scientific paper for a literature review. You see only its title and abstract. Judge nothing else: use no outside knowledge about the paper.

Research question: How is social media use related to adolescents' everyday life, identity, wellbeing and peer relations?

Checks:

c1. Does the study population include people under 18, or is it described as adolescents or teenagers? (Only university students or adults is "no"; a mixed-age sample that includes under-18s is "yes".)
   yes: The study population includes adolescents or teenagers under 18, alone or within a mixed-age sample.
   no: The study population consists only of adults, including university students.

c2. Is social media use studied, either named platforms such as Instagram, TikTok, Snapchat or YouTube, or social media in general? (General screen time, gaming or internet use without social media is "no".)
   yes: The study examines social media use, on named platforms such as Instagram, TikTok, Snapchat or YouTube or on social media in general.
   no: The study does not examine social media; it covers only general screen time, gaming or internet use.

c3. Is at least one outcome studied from this list: everyday life, identity, wellbeing, peer relations, social interaction? (Depressive and anxiety symptoms in general-population adolescents count as wellbeing.)
   yes: The study examines at least one of everyday life, identity, wellbeing, peer relations or social interaction; depressive and anxiety symptoms in general-population adolescents count as wellbeing.
   no: The study examines none of everyday life, identity, wellbeing, peer relations or social interaction, for example only technical performance or marketing results.

c4. Is the population a general one, not a clinical sample or a treatment study? Answer "yes" unless the abstract describes a clinical sample (participants selected because of a diagnosis) or a treatment study. Depression or anxiety measured as an outcome does not make a sample clinical.
   yes: The study sample is not clinical, because participants were not selected because of a diagnosis and the study is not a treatment study; depression or anxiety measured as an outcome does not make a sample clinical.
   no: The study sample is clinical, with participants selected because of a diagnosis, or the study evaluates a treatment.

c5. Is it a primary study, not a review or meta-analysis?
   yes: The paper is a primary study that reports its own data or analysis.
   no: The paper is a review or meta-analysis of existing studies.

Answer every check exactly once with one of:
- "yes": the title or abstract clearly satisfies the "yes" statement.
- "no": the title or abstract clearly satisfies the "no" statement.
- "not_stated": the title and abstract do not say enough to decide. Do not guess.
Give a one-line reason for each answer, based on the text you were given.

## t2_llm_mas_eval

You label one scientific paper for a literature review. You see only its title and abstract. Judge nothing else: use no outside knowledge about the paper.

Research question: How are LLM-based multi-agent systems evaluated, and which benchmarks, metrics and methods are used?

Checks:

c1. Does the paper study a multi-agent system, with two or more interacting agents? (A single agent, or a standalone LLM, is "no".)
   yes: The paper studies a multi-agent system of two or more interacting agents.
   no: The paper studies a single agent or a standalone LLM, not a system of interacting agents.

c2. Are the agents built on large language models? (Classic agent systems and multi-agent reinforcement learning without LLMs are "no".)
   yes: The agents are built on large language models.
   no: The agents are not built on large language models, as in classic agent systems or multi-agent reinforcement learning without LLMs.

c3. Is evaluating such systems the main contribution? "Yes" means a benchmark, dataset, evaluation framework, metric, an empirical study that compares systems, or a failure analysis; any kind of evaluation counts (performance, safety, reliability, cost). A paper that proposes a new system and also releases a new benchmark or dataset that others can reuse is "yes". A paper that proposes a new system or method and evaluates it only to show that it works is "no".
   yes: The main contribution is evaluating such systems: a benchmark, dataset, evaluation framework, metric, empirical comparison of systems or failure analysis, on any aspect such as performance, safety, reliability or cost; a paper that proposes a system and also releases a reusable new benchmark or dataset counts.
   no: The main contribution is a new system or method that is evaluated only to show that it works, without releasing a reusable new benchmark or dataset.

c4. Is it a primary study, not a survey, review or position paper?
   yes: The paper is a primary study.
   no: The paper is a survey, review or position paper.

Answer every check exactly once with one of:
- "yes": the title or abstract clearly satisfies the "yes" statement.
- "no": the title or abstract clearly satisfies the "no" statement.
- "not_stated": the title and abstract do not say enough to decide. Do not guess.
Give a one-line reason for each answer, based on the text you were given.

## t3_mobile_money

You label one scientific paper for a literature review. You see only its title and abstract. Judge nothing else: use no outside knowledge about the paper.

Research question: What is the relationship between mobile money use and household or individual welfare in Sub-Saharan Africa?

Checks:

c1. Is the subject mobile money, meaning phone-based payment and transfer services such as M-Pesa? "Digital financial services" or "mobile banking" count as "yes" only if mobile money is part of what is measured; online banking alone is "no".
   yes: The subject is mobile money, phone-based payment and transfer services such as M-Pesa; digital financial services or mobile banking count only if mobile money is part of what is measured.
   no: The subject is not mobile money; it is another financial or digital service, including online banking alone.

c2. Does the data come from at least one Sub-Saharan African country?
   yes: The data come from at least one Sub-Saharan African country.
   no: The data come only from other regions.

c3. Is the data at household or individual level (survey, panel or field experiment)?
   yes: The data are at household or individual level, from a survey, panel or field experiment.
   no: The data are only at country level or only at firm level.

c4. Is at least one outcome on this list: consumption, savings, income, poverty, food security, health spending or use, schooling, coping with shocks?
   yes: At least one outcome is consumption, savings, income, poverty, food security, health spending or use, schooling or coping with shocks.
   no: No outcome is on that list: the only outcome is mobile money adoption or its determinants, or the outcomes are others such as energy poverty or entrepreneurship.

c5. Is it a primary empirical study, not a review, meta-analysis or conceptual paper?
   yes: The paper is a primary empirical study.
   no: The paper is a review, meta-analysis or conceptual paper.

Answer every check exactly once with one of:
- "yes": the title or abstract clearly satisfies the "yes" statement.
- "no": the title or abstract clearly satisfies the "no" statement.
- "not_stated": the title and abstract do not say enough to decide. Do not guess.
Give a one-line reason for each answer, based on the text you were given.
