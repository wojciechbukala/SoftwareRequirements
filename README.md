## Repository purpose
Repository for problem formulations and requirements specifications for AI agents behaviour analysis, a master's thesis conducted by Wojciech Bukala.

## Master's Thesis Topic
Analysis of the impact of the degree of formalization of requirement specifications on the quality metrics of code generated using agent-based systems.

## Specification Requirements structure
Repository consists of several directories. Each directory corresponds to one programming problem an has a structure as below:
- CONTEXT.md - an explenation of the programming problem, can be seen as a task given by stakeholders to the developers team.
- REQ1.md - first form of the requirements specification - natural language specifiactaion without any specified structure.
- REQ2.md - second form of the requirements specification - document in a structure proposed by IEEE 29148 norm, but written in natural language only.
- REQ3.md - third form of the requirements specification - document in a structruture proposed by the norm with addtion UML diagrams (in Mermaid form).
- REQ4.md -
- Diagrams - UML diagrams created for a given task, attached to the 3rd form of specification.
- REQ3_human_readable.md - third form of the requirements specification with UML attached in the graphical form instead of Mermaid.

## Automation
Automation directory provides the bash scripts used during experiments in Linux Ubuntu OS environment. Scripts invoke agentic system in the isolated docker container. Each script copies the given requirement specification to the REQUIREMNTS.md file in the working directiory, and provides very simple prompt to the system:

**You are an expert software engineer. Read the requirements specification at REQUIREMENTS.md and implement the system in the current directory. Do not ask clarifying questions. Provide a summary of the work done in SUMMARY.md**

### Cluade Code
Claude code is defaultly invoked with the following arguments and options:
- --model claude-sonnet-4-6
- --permision-mode bypassPermissions
- p (prompt as above)

To run experiment pipeline with claude code system provide following commad:
*bash Automation/claude-code-run.sh -r "<RequirementsSpecificationPath> -n <NumberOfRun>

Number of runs is set for 3 as a default.

## AI usage
Following the princliple of full disclosure when working with GenAI, every usage of GenAI is listed below.
- Text correction (Cluade, Gemini)
- UML diagram correction (Claude)

## Author
Wojciech Bukała
263479
