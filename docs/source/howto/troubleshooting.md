# Troubleshooting
## Ontology Update after automatic creation
**This is only loosely related to pyirk**
When using Stafo to create a pyirk module (B), using entities from a different module (A), this creates a new valid pyirk module (B) which imports the other module (A). If one then updates the module A with e.g. functional relations of entities that are also used in B, this will result in a `FunctionalRelationError` when executing module B. This might be difficult to intuitively detect.

Solution: Recreate B with the new module A