USE clickbait;
GO

ALTER TABLE dbo.PredictionHistory ALTER COLUMN UserId INT NULL;
GO

ALTER TABLE dbo.PredictionHistory ADD GuestSessionId NVARCHAR(64) NULL;
GO

CREATE INDEX IX_PredictionHistory_GuestSessionId ON dbo.PredictionHistory (GuestSessionId);
GO