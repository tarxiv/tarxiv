# TarXiv

An archive of astronomical transients, with user annotations (tags, comments) layered on top.

## Language

**Object**:
An astronomical transient in the archive, identified by its TNS name (`source_id`, e.g. `2017dqn`).
_Avoid_: Source, transient, target

**Comment**:
A piece of plain text a user writes on one Object, visible to its Owner.
_Avoid_: Note, message, annotation

**Reply**:
A Comment whose parent is a top-level Comment on the same Object; it shares its parent's Owner.
Replies cannot themselves be replied to.

**Author**:
The user who wrote a Comment.
_Avoid_: Creator, poster

**Owner**:
The user or Team a Comment or Tag belongs to; it decides who can see it.
_Avoid_: Audience, scope

**Team owner**:
A Team member with the owner role, able to moderate the Team's Comments.

**Tombstone**:
A deleted top-level Comment whose text is removed but which stays in place because it has Replies.
