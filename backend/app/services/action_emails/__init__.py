"""Emails to the internal people on a record when someone acts on it (CEO 2026-10-31: "every single
action if not all of them should trigger an email to user, candidate, manager and so on").

One module per domain -- jobs, interviews, offers, submissions, timesheets, allocations, projects,
invoices, employees, candidates (recruiter / HR assignment) -- each with notify_<event>() called
after the caller's commit. The rules, shared through core.send():

  - staff only, through the working staff mail path (staff_mail_service.queue_staff_email);
    candidate-facing email goes through Thunder and is not sent from here;
  - one email per record, event and person: a deterministic key, so a retry never mails twice;
  - the person who did it is never emailed about their own action;
  - each person gets one email naming every role they hold on the record;
  - a failure to queue never undoes the action: it is logged with the stack and the record stays.
"""
