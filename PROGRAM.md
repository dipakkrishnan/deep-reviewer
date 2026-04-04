# Expert Reviews as a Service

## Problem

Increasingly, knowledge workers are generating artifacts with the help of AI. Artifacts could be code, papers, designs, art and many other outputs. Often, in the process of generating an artifact, humans understand the domain more deeply. The process of __doing__ transforms high-level problem understanding into detailed mental models. 

AI is now the "executor" for a large number of knowledge work tasks. Knowledge work tasks typically have an artifact layer. The artifact is the output of the task that solves a larger problem (the above referenced code, paper, design etc). Since AI handles execution, there is an understanding gap that emerges for the human builder. Delegating to AI speeds execution, but once it comes time to review the work, a user may have to "re-learn" the topic and carefully review through the artifact to make sure it is error-free. This reframes the problem of knowledge to work to minimal generation cost and huge review cost. The "volume" of edits goes up and multiple passes are required before an artifact is of passable quality.

Particularly with paper review, the problem is that tasks require expert input. Using a niche economic theorem requires an expert economist to: check the math, stress test how the theorem flows in the context of the paper's thesis, and even if the thesis and downstream application of the theorem even make sense. The expert economist encodes __judgement and taste__ - on the level of "Is this problem even possible to solve? Is this the right frame of reference? Is the math correct? What similar papers exist to this and where did they fall short? What experience do I have that can reduce pitfalls for the artifact I'm reading?". Either users have to get reviews from experts explicitly or have to self-learn the concepts and do a best-effort pass with the context they have. This context gathering effort increases review time significantly and elongates the time to ship an artifact.

## Solution

Code reviews are standard practice today - and companies have made inroads on cracking the review problem there. Cursor BugBot is an example. However, for papers you often want expert reviews. Catching errors requires a careful eye and multiple rounds of edits. __To reduce the volume of edits that a user must make, the idea is a simple service that offers deep, expert reviews of papers. These reviews find flaws, both obvious and opaque, that help the author reduce errors in less passes than if they did manual review OR a cursory review using Claude or ChatGPT's chat functionalities with file upload.__

## UX

The user uploads a PDF or Arxiv link that they want reviewed in a clean GUI and clicks a review button. The system acknowledges the task - and proceeds to ask the user questions about the artifact to learn more about the parameters of the review task. Once the questions are answered, the system grinds on producing a review and renders it once done. If the system has serviced the user before, it should update a wiki-style entry about the user and their judgment, taste and previously reviewed artifacts.

## Review Modes

`quick`
`standard`
`deep`

These are user-configurable settings that allow the system to determine the depth of the agent network or swarm that takes on the review task. These encode default swarm sizes at each level.

## System

The system is multi-agent. Once an artifact has been downloaded, the system is first responsible for asking the user questions about the task in an attempt to gain a mental model of the goal of the artifact's creation. It asks the user for information supplements in the form of github repos, relevant authors, code examples, topics to research. It's a user "interview" that aligns the system with the user's goal. That user interview is checkpointed to a file system, as well as in the context window via the messages between user and assistant.

Once the interview concludes, an orchestrator agent breaks down the artifact review task into a dynamic number of sub-goals that are domain-specific and targeted. These sub-goals are picked up by subagents. For example, the orchestrator could solicit a theorem-review subagent, a current relevant literature searcher subagent, a current relevant literature synthesizing subagent, a logical error finding subagent in the course of context gathering to review a mathematics paper. Each subagent is an "expert" - and instructed to produce research with "expert" quality. Subagent goals need not be generic, they can be highly niche if needed - e.g. provide a cutting edge breakdown of tropical geometry or descriptive set theory.. Once context gathering completes, the main orchestrator produces a high-quality "peer-review"-like artifact. This is a text report rendered directly in the GUI. 

The orchestrator is highly powerful - it can "self-play" adversarially to take opposing sides of the review artifact to error check itself. It can write code to implement parts of the artifact if it so wishes to "experiment" with the ideas, gain intuition and find inconsistencies - as a researcher would. The process of taking a theorem and translating it to code is actually a useful hot point for finding inaccuracies in the first place.

## Tech Stack

- Python backend - preference for flat structure with core agent functionality and typed Pydantic models for clarity of API boundaries.
- FastAPI API layer to expose core-review functionality
- Simple, beautiful and intuitive TypeScript frontend that supports the interview functionality and review of artifact.
- File-system available to the agent, file system tools, web search, web fetch tools

## Monitoring and Observability

Each review run gets metadata logged (how many agents / subagents, task type, cost in usd).

## Product Inspo: Agent Council or "Mixture of Experts"

The best ideas from "agent councils" or MoE combine the ideas of specialization and throwing lots of tokens at problems with different weight sets as a way to solicit diverse agent opinions. I think this can be utilized for expert reviews as well. MoE's exploit sparsity to make inference much more efficient, but as a side product, create sub-networks with expert specialization. In the longer term, this product could create sub-networks of agent knowledge that improves review quality over time. When it's not reviewing, it's boning up on topics relevant to it's subagent goal to do a better job the next time.
