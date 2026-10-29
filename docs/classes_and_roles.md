# Classes and roles

## For students

You belong to one or more **classes**. Your teacher (and a facilitator, if your
class has one) can open your projects to help you, but cannot change them or
publish them: your work stays yours. Other students cannot see your projects.

## For teachers

1. Ask the administrator to set your **role in class** to `teacher` (Users page).
2. Open the menu with your name (top right), choose **Classes**, type a name (for example `3B`) and press **Make class**.
3. Add each student by username or email. Only accounts whose role in class is
   `student` can be added as students.
4. **Students' projects** lists their projects. Open one to look at it; it is
   read-only for you.

Removing a student from the class ends your view of their work at once.

| Who | Makes classes | Adds students | Adds teachers/facilitators | Reads students' work | Changes or publishes it |
| --- | --- | --- | --- | --- | --- |
| student | no | no | no | own only | own only |
| teacher | yes | in own classes | no | in own classes | no |
| facilitator | no | no | no | in their classes | no |
| administrator | yes | yes | yes | everything | everything |

A **facilitator** (a classroom assistant, a visiting tutor) is added to a class by
an administrator and can look at the students' work, nothing more.

**service** accounts are for scripts: they cannot sign in, only use API tokens.

These roles stay in the kit. The role shared with the Cartridge Store
(`user`, `publisher`, `admin`) is separate: a teacher who should publish needs
`publisher` there too, and even then publishes only their own work.

Design: `adr/0016-academic-identity-and-scoped-roles.md`.
