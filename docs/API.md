# Learnify API

Base: `http://127.0.0.1:8021` — success envelope `{success, data, error}`; auth routes return `{user, session}` directly.
170 operations across 14 tags.

## ?

### `POST /api/auth/change-password`
- Change Password
- body: `current_password:string`, `new_password:string`

### `GET /api/auth/confirm`
- Confirm
- query: `code?`, `access_token?`

### `POST /api/auth/login`
- Login
- body: `email:string`, `password:string`

### `GET /api/auth/me`
- Me

### `PUT /api/auth/profile`
- Update Profile
- body: `name?:any`, `department?:any`, `designation?:any`, `headline?:any`, `bio?:any`, `phone?:any`, `language?:any`

### `POST /api/auth/register`
- Register
- body: `email:string`, `password:string`, `name:string`, `role?:string`, `language?:string`, `invite?:string`

### `POST /api/v1/notifications/mark-all-read`
- Mark All Read

### `GET /api/v1/notifications/my`
- My Notifications
- query: `unread_only?`, `limit?`

### `GET /api/v1/notifications/unread-count`
- Unread Count

### `PATCH /api/v1/notifications/{notification_id}/read`
- Mark Read
- path: `notification_id`

### `GET /health`
- Health

## admin

### `POST /api/v1/admin/approve`
- Approve
- body: `user_id:string`, `reason?:string`

### `GET /api/v1/admin/audit`
- Audit Log
- query: `action?`, `actor_id?`, `limit?`, `offset?`

### `GET /api/v1/admin/dashboard`
- Dashboard

### `GET /api/v1/admin/invites`
- List Invites

### `POST /api/v1/admin/invites`
- Create Invite
- body: `email?:string`, `note?:string`, `days?:integer`, `max_uses?:integer`

### `DELETE /api/v1/admin/invites/{token}`
- Revoke Invite
- path: `token`

### `POST /api/v1/admin/notifications`
- Send Notification
- body: `title:string`, `message?:string`, `link?:string`, `type?:string`, `audience?:string`, `user_ids?:array[string]`

### `GET /api/v1/admin/notifications/audiences`
- Notification Audiences

### `GET /api/v1/admin/pending`
- Pending Users

### `POST /api/v1/admin/reject`
- Reject Registration
- body: `user_id:string`, `reason?:string`

### `POST /api/v1/admin/role`
- Change Role
- body: `user_id:string`, `role:string`

### `GET /api/v1/admin/stats`
- Platform Stats

### `POST /api/v1/admin/suspend`
- Suspend
- body: `user_id:string`, `reason?:string`

### `POST /api/v1/admin/unsuspend`
- Unsuspend

### `GET /api/v1/admin/users`
- List Users
- query: `role?`, `status?`, `q?`, `limit?`, `offset?`

### `DELETE /api/v1/admin/users/{user_id}`
- Delete User
- path: `user_id`

### `GET /api/v1/admin/users/{user_id}`
- User Detail
- path: `user_id`

## ai

### `GET /api/v1/ai/drafts`
- List Drafts
- query: `kind?`, `status?`, `limit?`

### `POST /api/v1/ai/drafts/bulk-publish`
- Bulk Publish
- body: `target_id:string`

### `POST /api/v1/ai/drafts/publish-selected`
- Publish Selected

### `DELETE /api/v1/ai/drafts/{draft_id}`
- Discard Draft
- path: `draft_id`

### `GET /api/v1/ai/drafts/{draft_id}`
- Get Draft
- path: `draft_id`

### `PUT /api/v1/ai/drafts/{draft_id}`
- Edit Draft
- path: `draft_id`
- body: `text:string`, `options:array[string]`, `correct_index:integer`, `explanation?:string`, `difficulty?:string`, `topic_id?:string`

### `POST /api/v1/ai/drafts/{draft_id}/publish`
- Publish One
- path: `draft_id`
- body: `target_id:string`, `sort_order?:integer`

### `POST /api/v1/ai/generate-questions`
- Generate
- body: `subject_id?:string`, `topic_ids?:array[string]`, `count?:integer`, `difficulty?:string`, `kind?:string`, `context?:string`

### `POST /api/v1/ai/personalise-report`
- Personalise
- body: `report_id:string`

### `GET /api/v1/ai/status`
- Ai Status

## assessments

### `GET /api/v1/assessments`
- List Assessments
- query: `status?`, `subject_id?`, `course_id?`, `mine?`, `q?`, `limit?`

### `POST /api/v1/assessments`
- Create
- body: `title:string`, `description?:string`, `subject_id?:string`, `course_id?:string`, `duration_minutes?:integer`, `max_score?:integer`, `passing_score?:integer`, `deadline_at?:string`

### `DELETE /api/v1/assessments/{aid}`
- Delete
- path: `aid`

### `GET /api/v1/assessments/{aid}`
- Get Assessment
- path: `aid`

### `PUT /api/v1/assessments/{aid}`
- Update
- path: `aid`
- body: `title:string`, `description?:string`, `subject_id?:string`, `course_id?:string`, `duration_minutes?:integer`, `max_score?:integer`, `passing_score?:integer`, `deadline_at?:string`

### `GET /api/v1/assessments/{aid}/attempts`
- All Attempts
- path: `aid`
- query: `status?`, `limit?`

### `GET /api/v1/assessments/{aid}/attempts/mine`
- My Attempts
- path: `aid`

### `POST /api/v1/assessments/{aid}/attempts/{attempt_id}/void`
- Void Attempt
- path: `aid`, `attempt_id`

### `POST /api/v1/assessments/{aid}/end`
- End Now
- path: `aid`

### `GET /api/v1/assessments/{aid}/live`
- Live Attempts
- path: `aid`

### `POST /api/v1/assessments/{aid}/progress`
- Save Progress
- path: `aid`
- body: `responses?:array[object]`, `duration_seconds?:integer`

### `GET /api/v1/assessments/{aid}/questions`
- List Questions
- path: `aid`

### `POST /api/v1/assessments/{aid}/questions`
- Add Question
- path: `aid`
- body: `text:string`, `explanation?:string`, `difficulty?:string`, `topic_id?:string`, `points?:number`, `options?:array[object]`

### `PUT /api/v1/assessments/{aid}/questions-order`
- Reorder
- path: `aid`

### `POST /api/v1/assessments/{aid}/questions/bulk`
- Add Questions Bulk
- path: `aid`

### `DELETE /api/v1/assessments/{aid}/questions/{question_id}`
- Remove Question
- path: `aid`, `question_id`

### `POST /api/v1/assessments/{aid}/reject`
- Reject
- path: `aid`

### `POST /api/v1/assessments/{aid}/release`
- Release
- path: `aid`

### `POST /api/v1/assessments/{aid}/reopen`
- Reopen
- path: `aid`

### `POST /api/v1/assessments/{aid}/start`
- Start
- path: `aid`

### `POST /api/v1/assessments/{aid}/submit`
- Submit
- path: `aid`

### `POST /api/v1/assessments/{aid}/submit-attempt`
- Submit Attempt
- path: `aid`
- body: `responses?:array[object]`, `duration_seconds?:integer`

## competency

### `GET /api/v1/competency/catalog`
- Catalog

### `GET /api/v1/competency/mine`
- My Competencies

### `PUT /api/v1/competency/mine`
- Upsert Self
- body: `items?:array[obj]`

### `DELETE /api/v1/competency/mine/{competency_id}`
- Remove Self
- path: `competency_id`

### `GET /api/v1/competency/trainers/{subject_id}`
- Ranked Trainers
- path: `subject_id`
- query: `limit?`

### `GET /api/v1/competency/trainers/{trainer_id}/profile`
- Trainer Competency Profile
- path: `trainer_id`

### `POST /api/v1/competency/verify`
- Verify Competency
- body: `trainer_id:string`, `competency_id:string`, `verified?:boolean`

## courses

### `GET /api/v1/courses`
- List Courses
- query: `status?`, `subject_id?`, `q?`, `mine?`, `limit?`

### `POST /api/v1/courses`
- Create Course
- body: `title:string`, `subject_id?:string`, `level?:string`, `description?:string`, `duration_hours?:number`, `cover_image_url?:string`

### `GET /api/v1/courses/{course_id}`
- Get Course
- path: `course_id`

### `DELETE /api/v1/courses/{course_id}/attachments/{attachment_id}`
- Delete Attachment
- path: `course_id`, `attachment_id`

### `POST /api/v1/courses/{course_id}/enroll`
- Enroll
- path: `course_id`

### `GET /api/v1/courses/{course_id}/enrollments`
- List Enrollments
- path: `course_id`
- query: `limit?`

### `POST /api/v1/courses/{course_id}/leave`
- Leave
- path: `course_id`

### `POST /api/v1/courses/{course_id}/modules`
- Add Module
- path: `course_id`
- body: `title:string`, `description?:string`

### `PUT /api/v1/courses/{course_id}/modules-order`
- Reorder Modules
- path: `course_id`
- body: `order?:array[string]`

### `DELETE /api/v1/courses/{course_id}/modules/{module_id}`
- Delete Module
- path: `course_id`, `module_id`

### `PUT /api/v1/courses/{course_id}/modules/{module_id}`
- Update Module
- path: `course_id`, `module_id`
- body: `title:string`, `description?:string`

### `GET /api/v1/courses/{course_id}/outline`
- Course Outline
- path: `course_id`

### `POST /api/v1/courses/{course_id}/reject`
- Reject Course
- path: `course_id`
- body: `status:string`

### `POST /api/v1/courses/{course_id}/release`
- Release Course
- path: `course_id`

### `POST /api/v1/courses/{course_id}/slots`
- Add Slot
- path: `course_id`
- body: `module_id:string`, `title:string`, `kind?:string`

### `DELETE /api/v1/courses/{course_id}/slots/{slot_id}`
- Delete Slot
- path: `course_id`, `slot_id`

### `GET /api/v1/courses/{course_id}/slots/{slot_id}`
- Get Slot
- path: `course_id`, `slot_id`

### `PUT /api/v1/courses/{course_id}/slots/{slot_id}`
- Update Slot
- path: `course_id`, `slot_id`
- body: `title?:string`, `kind?:string`, `body?:string`, `video_source?:string`, `youtube_url?:string`, `storage_path?:string`, `duration_seconds?:integer`

### `GET /api/v1/courses/{course_id}/slots/{slot_id}/attachments`
- List Attachments
- path: `course_id`, `slot_id`

### `POST /api/v1/courses/{course_id}/slots/{slot_id}/attachments`
- Add Attachment
- path: `course_id`, `slot_id`
- body: `storage_path:string`, `filename:string`, `mime?:string`, `size_bytes?:integer`, `library_item_id?:string`

### `PUT /api/v1/courses/{course_id}/slots/{slot_id}/link-test`
- Link Test
- path: `course_id`, `slot_id`
- body: `linked_test_type?:string`, `linked_test_id?:string`

### `POST /api/v1/courses/{course_id}/status`
- Set Status
- path: `course_id`
- body: `status:string`

### `POST /api/v1/courses/{course_id}/step/{n}`
- Goto Step
- path: `course_id`, `n`

### `PUT /api/v1/courses/{course_id}/step1`
- Update Step1
- path: `course_id`
- body: `title:string`, `subject_id?:string`, `level?:string`, `description?:string`, `duration_hours?:number`, `cover_image_url?:string`

### `POST /api/v1/courses/{course_id}/submit`
- Submit For Release
- path: `course_id`

### `GET /api/v1/courses/{course_id}/wizard`
- Wizard State
- path: `course_id`

## feed

### `GET /api/v1/feed`
- My Feed
- query: `post_type?`, `q?`, `limit?`, `offset?`

### `POST /api/v1/feed`
- Create Post
- body: `type:string`, `title:string`, `body?:string`, `link?:string`, `image_url?:string`, `target_roles?:array[string]`, `pinned?:boolean`, `published?:boolean`

### `GET /api/v1/feed/all/manage`
- Manage List
- query: `post_type?`, `limit?`

### `GET /api/v1/feed/types`
- Post Types

### `DELETE /api/v1/feed/{post_id}`
- Delete Post
- path: `post_id`

### `GET /api/v1/feed/{post_id}`
- Get Post
- path: `post_id`

### `PUT /api/v1/feed/{post_id}`
- Update Post
- path: `post_id`
- body: `type:string`, `title:string`, `body?:string`, `link?:string`, `image_url?:string`, `target_roles?:array[string]`, `pinned?:boolean`, `published?:boolean`

### `POST /api/v1/feed/{post_id}/pin`
- Toggle Pin
- path: `post_id`

## feedback

### `POST /api/v1/feedback/content`
- Rate Content
- body: `content_type:string`, `content_id:string`, `rating:integer`, `comment?:string`

### `GET /api/v1/feedback/content/{content_type}/{content_id}`
- Content Feedback
- path: `content_type`, `content_id`

### `POST /api/v1/feedback/course`
- Rate Course
- body: `course_id:string`, `rating:integer`, `comment?:string`

### `GET /api/v1/feedback/course/{course_id}`
- Course Feedback
- path: `course_id`

### `GET /api/v1/feedback/course/{course_id}/mine`
- My Course Feedback
- path: `course_id`

### `GET /api/v1/feedback/my`
- My Feedback
- query: `limit?`

## library

### `GET /api/v1/library`
- List Library
- query: `file_type?`, `subject_id?`, `mine?`, `q?`, `limit?`

### `POST /api/v1/library`
- Create Item
- body: `title:string`, `description?:string`, `file_type:string`, `subject_id?:string`, `youtube_url?:string`, `duration_seconds?:integer`

### `DELETE /api/v1/library/files`
- Delete File
- query: `path`, `bucket?`

### `GET /api/v1/library/files/sign`
- Signed Url
- query: `path`, `bucket?`, `expires?`

### `POST /api/v1/library/upload`
- Upload

### `DELETE /api/v1/library/{item_id}`
- Delete Item
- path: `item_id`

### `GET /api/v1/library/{item_id}`
- Get Item
- path: `item_id`

### `PUT /api/v1/library/{item_id}`
- Update Item
- path: `item_id`
- body: `title:string`, `description?:string`, `file_type:string`, `subject_id?:string`, `youtube_url?:string`, `duration_seconds?:integer`

### `POST /api/v1/library/{item_id}/attach-file`
- Attach File
- path: `item_id`

### `GET /api/v1/library/{item_id}/stats`
- Item Stats
- path: `item_id`

## participation

### `POST /api/v1/participation/complete`
- Complete Slot
- body: `slot_id:string`

### `GET /api/v1/participation/course/{course_id}`
- Course Progress
- path: `course_id`

### `POST /api/v1/participation/enrollment/{course_id}/sync`
- Sync Enrollment
- path: `course_id`

### `GET /api/v1/participation/my`
- My Activity
- query: `limit?`

### `POST /api/v1/participation/progress`
- Save Progress
- body: `slot_id:string`, `position_seconds:integer`, `duration_seconds?:integer`, `watched_delta?:integer`

### `GET /api/v1/participation/slot/{slot_id}`
- Slot Progress
- path: `slot_id`

### `GET /api/v1/participation/stats`
- My Stats

## profiles

### `GET /api/v1/profiles/me`
- My Profile

### `PUT /api/v1/profiles/me`
- Update My Profile
- body: `education?:array[obj]`, `qualifications?:array[obj]`, `experience?:array[obj]`, `interests?:array[string]`, `skills?:array[obj]`, `certificates?:array[obj]`

### `GET /api/v1/profiles/{user_id}`
- View Profile
- path: `user_id`

## questionnaires

### `GET /api/v1/questionnaires`
- List Questionnaires
- query: `status?`, `subject_id?`, `mine?`, `q?`, `limit?`

### `POST /api/v1/questionnaires`
- Create
- body: `title:string`, `description?:string`, `subject_id?:string`, `topic_id?:string`, `course_id?:string`, `deadline_at?:string`, `duration_minutes?:integer`, `max_attempts?:integer`

### `DELETE /api/v1/questionnaires/{qid}`
- Delete
- path: `qid`

### `GET /api/v1/questionnaires/{qid}`
- Get Questionnaire
- path: `qid`

### `PUT /api/v1/questionnaires/{qid}`
- Update
- path: `qid`
- body: `title:string`, `description?:string`, `subject_id?:string`, `topic_id?:string`, `course_id?:string`, `deadline_at?:string`, `duration_minutes?:integer`, `max_attempts?:integer`

### `GET /api/v1/questionnaires/{qid}/attempts`
- All Attempts
- path: `qid`
- query: `status?`, `limit?`

### `GET /api/v1/questionnaires/{qid}/attempts/mine`
- My Attempts
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/attempts/{attempt_id}/void`
- Void Attempt
- path: `qid`, `attempt_id`

### `POST /api/v1/questionnaires/{qid}/end`
- End Now
- path: `qid`

### `GET /api/v1/questionnaires/{qid}/live`
- Live Attempts
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/progress`
- Save Progress
- path: `qid`
- body: `responses?:array[object]`, `duration_seconds?:integer`

### `GET /api/v1/questionnaires/{qid}/questions`
- List Questions
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/questions`
- Add Question
- path: `qid`
- body: `text:string`, `explanation?:string`, `difficulty?:string`, `topic_id?:string`, `points?:number`, `options?:array[object]`

### `PUT /api/v1/questionnaires/{qid}/questions-order`
- Reorder
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/questions/bulk`
- Add Questions Bulk
- path: `qid`

### `DELETE /api/v1/questionnaires/{qid}/questions/{question_id}`
- Remove Question
- path: `qid`, `question_id`

### `POST /api/v1/questionnaires/{qid}/reject`
- Reject
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/release`
- Release
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/reopen`
- Reopen
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/start`
- Start
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/submit`
- Submit
- path: `qid`

### `POST /api/v1/questionnaires/{qid}/submit-attempt`
- Submit Attempt
- path: `qid`
- body: `responses?:array[object]`, `duration_seconds?:integer`

## reports

### `GET /api/v1/reports`
- List Reports
- query: `subject_id?`, `kind?`, `mine?`, `trainee_id?`, `limit?`, `offset?`

### `DELETE /api/v1/reports/benchmarks/{benchmark_id}`
- Delete Benchmark
- path: `benchmark_id`

### `GET /api/v1/reports/benchmarks/{subject_id}`
- List Benchmarks
- path: `subject_id`

### `PUT /api/v1/reports/benchmarks/{subject_id}`
- Upsert Benchmark
- path: `subject_id`
- body: `topic_id?:string`, `industry_standard:string`, `expected_proficiency?:integer`, `notes?:string`

### `POST /api/v1/reports/generate`
- Generate
- body: `attempt_id:string`, `attempt_kind?:string`

### `GET /api/v1/reports/stats/summary`
- Summary
- query: `subject_id?`

### `GET /api/v1/reports/stats/weak-topics`
- Weak Topics
- query: `subject_id?`, `limit?`

### `GET /api/v1/reports/{report_id}`
- Get Report
- path: `report_id`

## subjects

### `GET /api/v1/subjects`
- List Subjects
- query: `q?`, `active_only?`

### `POST /api/v1/subjects`
- Create Subject
- body: `code:string`, `name:string`, `category?:string`, `description?:string`

### `POST /api/v1/subjects/competencies`
- Create Competency
- body: `name:string`, `description?:string`

### `DELETE /api/v1/subjects/topics/{topic_id}`
- Delete Topic
- path: `topic_id`

### `GET /api/v1/subjects/with-topics`
- Subjects With Topics

### `DELETE /api/v1/subjects/{subject_id}`
- Delete Subject
- path: `subject_id`

### `PUT /api/v1/subjects/{subject_id}`
- Update Subject
- path: `subject_id`
- body: `code:string`, `name:string`, `category?:string`, `description?:string`

### `GET /api/v1/subjects/{subject_id}/competencies`
- List Subject Competencies
- path: `subject_id`

### `POST /api/v1/subjects/{subject_id}/competencies`
- Link Competency
- path: `subject_id`
- body: `competency_id:string`, `required_weight?:number`

### `DELETE /api/v1/subjects/{subject_id}/competencies/{competency_id}`
- Unlink Competency
- path: `subject_id`, `competency_id`

### `GET /api/v1/subjects/{subject_id}/topics`
- List Topics
- path: `subject_id`

### `POST /api/v1/subjects/{subject_id}/topics`
- Add Topic
- path: `subject_id`
- body: `name:string`, `description?:string`

### `POST /api/v1/subjects/{subject_id}/topics/bulk`
- Add Topics Bulk
- path: `subject_id`
- body: `names?:array[string]`
