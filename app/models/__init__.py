"""数据模型包"""
from app.models.user import User, UserRole
from app.models.class_model import Class, class_student, class_teacher
from app.models.assignment import Assignment, AssignmentGrade
from app.models.submission import Submission
from app.models.notification import Notification
from app.models.makeup_request import MakeupRequest
from app.models.team import (
    MajorAssignment, Team, TeamMember,
    TeamInvitation, LeaveTeamRequest, DissolveTeamRequest,
    Stage, DivisionRole, TeamDivision,
    TeamTask, TaskProgress,
    MajorAssignmentAttachment, MajorAssignmentLink
)

__all__ = [
    'User', 'UserRole',
    'Class', 'class_student', 'class_teacher',
    'Assignment', 'AssignmentGrade',
    'Submission',
    'Notification',
    'MakeupRequest',
    'MajorAssignment', 'Team', 'TeamMember',
    'TeamInvitation', 'LeaveTeamRequest', 'DissolveTeamRequest',
    'Stage', 'DivisionRole', 'TeamDivision',
    'TeamTask', 'TaskProgress',
    'MajorAssignmentAttachment', 'MajorAssignmentLink'
]
