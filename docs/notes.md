# Notes for docs

## Main 
- Use optional dependencies for required pakages
- Add link to preprint in the main motivation section
- Remove sentences *Nevertheless some usefulness cannot be excluded.* in Status
- Add some introductory sentences about the ideas behind pyirk, especially about the role and meaning of Entities, 
  Statements and their friends.

# User

- Maybe start the user guide with a short "getting started" tutorial before going into all details 
- Explain what keys are before 5 variants og them are shown
- State all ETypes (Item, Relation and Literal) and explain them
- Do Statements have keys too? If yes, explain their SType Enum, too.
- Move section 'Patterns for Knowledge Representation in Pyirk' to the top
- In that section: Refactor sentences in enumerations that show all instances of entities and link to the classes. 
- Introduce a simple example (with a nice picture) and illustrate the meanings of the following section based on that example.
- The 'note' at the end of the Item section is rather confusing, elaborate on that.
- Concerning the __call__ method: Give motivating example and shorten text about the inner workings just tell
  the user what to do to make the thing callable
- Give an example of how adding a convenience method actually makes things easier, the internal get_arguments call 
  does not fulfill this purpose
- Relations: Start with what they are (Graph analogy) and then explain the details, give example for instantiation 
- Elaborate more on Literals, usage remains unclear
- Move first paragraph from qualifiers section to statement section, try to avoid forward references (qualifiers)
- Note about inverses is not helpful, either elaborate more or remove
- Split explanation sentence for Statement section at 'because' and move that to the beginning of qualifiers
- Final example in qualifier section remains nebulous
- Scopes, Basics: Name the theorem, again: Note is not helpful
- Introduce universally quantified instances before using them in the scope cm example 
- Use references to the actual code to prevent problems in the future
- Operators: Add explanation and try to find shorter example, explain domain_of_argument-foo, do not use OCSE code
- Formulas: No OCSE code
- Modules and packages: Explain what an URI is