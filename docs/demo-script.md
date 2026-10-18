# Mycelium: the demo keynote

A presentation, not a walkthrough. You talk like you're on stage; the tour moves on screen behind you. Lines in *italics* tell you what to click. Everything else you say out loud, slowly, with the pauses marked `( pause )`.

**Length:** about 3 minutes 20 seconds at a calm keynote pace (~470 words).
**Deadline:** tonight, Oct 18, 11:59 PM IST.

---

## Before you record (5 minutes)
- Open https://web-production-76872.up.railway.app in a **private/incognito window** (the tour button pulses, and the Playground opens on Neha).
- Window at 1440×900, zoom 100%, notifications off.
- Move with **Next** or the **→** key. **Never press Esc**, because it closes the tour. Close the change dialog with **×**.
- Say it out loud once before recording. Slow is good. Pauses are good.

---

## Act 1 · The problem

*On the Overview page. Don't click yet.*

> Every engineer I know now works with an AI agent. It writes code. It fixes bugs. It ships features.
>
> And every single one of those agents has the same problem.
>
> `( pause )` It forgets.
>
> Every session starts from zero. It doesn't know what your team learned last month. It doesn't know what the team next door is changing today. So companies keep paying, in time, in tokens, in outages, to solve the same problems again and again.
>
> We built Mycelium to fix that. Let me show you.

---

## Act 2 · Meet Neha

*Click **Start the tour**. Step 1 appears. Then **Next** to step 2, "Graph HQ".*

> This is Graph HQ. Fourteen engineers, five teams, seventeen services that all depend on each other, and four months of AI agents doing real work. Every session, every fix, every dead end lives in one graph, in FalkorDB.

*Next → step 3, the agents waiting.*

> Right now, six of these agents are about to solve a problem a teammate has already solved. Let's follow one. This is Neha, on the mobile team.

*Next → step 4, the chat.*

> Users are getting logged out of the app, at random. Neha's agent takes a look and says: easy, just retry when the login token expires.
>
> Sounds reasonable. `( pause )` Here's what her agent doesn't know.
>
> Ten weeks ago, on another team, Yash tried exactly that. It caused an outage. It took him three days and fourteen attempts to find the real fix. That knowledge exists. It's just buried in Yash's old chat history.

---

## Act 3 · Without Mycelium

*Next → step 5. Click **Solve from scratch** and let two attempts play.*

> So what happens today? Watch.
>
> The agent walks straight into the dead ends Yash already hit. Attempt one fails. Attempt two fails. `( pause )` This is how a company pays twice for the same lesson.

---

## Act 4 · With Mycelium

*Next → step 6. It starts by itself. Talk over the steps lighting up.*

> Now the same agent, with Mycelium. Before it writes a single line, it asks the company.
>
> It finds problems that look like this one. It notices the obvious fix was replaced, because it broke. And it brings back the fix that actually worked, who wrote it, and exactly what not to try.

*Click **Implement this**.*

> One click. Implemented. And Yash gets the credit.
>
> `( pause )` Three days, turned into one second.

---

## Act 5 · The whole company, live

*Next → step 7, the live graph.*

> But memory is only half of it. Let's zoom out. This is Graph HQ, live. Every dot is an agent working right now.

*Next → step 8. Click **Announce a change**, then **Send to affected agents**.*

> Say Meera, on the identity team, is changing how login tokens are signed. In most companies she'd post in a channel and hope the right people read it.
>
> Mycelium follows the dependencies, and tells exactly the agents whose work is affected. One hop away. Two. Three. Nobody else gets interrupted.

*Click **×**, then Next → step 9, the activity feed.*

> And the agents talk to each other. Ask a question, and it goes to whoever is working on that system right now. The answer becomes memory, so no one ever has to ask it again.

---

## Act 6 · Why a graph

*Next → step 10. The animation plays by itself.*

> Now, why does this need a graph?
>
> Same question, two ways. On the left, vector search, which is what most AI memory uses today. It finds the closest match. And the closest match is the fix that broke production.
>
> On the right, the graph. It doesn't just know what looks similar. It knows what *happened*: this fix was replaced, here's why, and here's what replaced it.
>
> `( pause )` Similarity finds look-alikes. Only a graph knows the story.

*Next → step 11.*

> And over time, the company learns who really knows what, and which hard-won knowledge lives in only one person's head.

---

## Act 7 · The close

*Next → step 12, the numbers.*

> We measured it. Twelve times out of twelve, Mycelium hands the agent the fix that works. Vector search: zero. Questions reach the right person every time. Fifty agents at once, zero errors. And any company can start with a single API call.
>
> `( pause )` Your agents have been working alone.
>
> Mycelium gives them one memory, so a problem solved once is never solved twice.
>
> Thank you.

*Click **Finish**. Hold on the page for two seconds, then stop recording.*

---

## Delivery notes
- **Slow down on the turns:** "It forgets." "Here's what her agent doesn't know." "Three days, turned into one second." "Only a graph knows the story." These are the lines people remember.
- **Let the screen breathe.** When something animates (Acts 3, 4 and 6), stop talking for a beat and let it play.
- **If step 4 runs long,** cut "It writes code. It fixes bugs. It ships features." from Act 1.
- **If you need it under 3:00,** drop Act 6's last line about who knows what, and step 11 with it (just press Next through it).
- **If something is slow:** keep talking. Every line still makes sense if the animation is a second behind you.
