CREATE DATABASE clickbait;
GO

USE clickbait;
GO

CREATE TABLE dbo.Users (
    UserId INT IDENTITY(1,1) PRIMARY KEY,
    Username NVARCHAR(80) NOT NULL UNIQUE,
    PasswordHash NVARCHAR(300) NOT NULL,
    Role NVARCHAR(20) NOT NULL CONSTRAINT CK_Users_Role CHECK (Role IN ('user', 'admin')) DEFAULT 'user',
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE dbo.PredictionHistory (
    HistoryId BIGINT IDENTITY(1,1) PRIMARY KEY,
    UserId INT NOT NULL REFERENCES dbo.Users(UserId) ON DELETE CASCADE,
    Headline NVARCHAR(500) NOT NULL,
    Label NVARCHAR(40) NOT NULL,
    ClickbaitProbability FLOAT NOT NULL,
    Confidence FLOAT NOT NULL,
    ResultJson NVARCHAR(MAX) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- Initial administrator: username admin, password admin1109.
INSERT INTO dbo.Users (Username, PasswordHash, Role)
VALUES ('admin', '260000$4c8c2f4e14dc2f1b1d6a0c4e4b6cb5e4$ab9856184ebef10bd2a3a897e71909de4f782d9f4e223d735828373bbdcb77f8', 'admin');
GO