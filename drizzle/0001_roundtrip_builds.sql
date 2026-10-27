CREATE TABLE `rt_build` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`budget` integer DEFAULT 10000 NOT NULL,
	`created_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`updated_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL
);
--> statement-breakpoint
CREATE TABLE `rt_build_path` (
	`build_id` text NOT NULL,
	`path_id` text NOT NULL,
	PRIMARY KEY(`build_id`, `path_id`),
	FOREIGN KEY (`build_id`) REFERENCES `rt_build`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`path_id`) REFERENCES `rt_path`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `rt_leg` (
	`sleeve_id` text NOT NULL,
	`expiry` text NOT NULL,
	`strike` real NOT NULL,
	`kind` text NOT NULL,
	`side` integer NOT NULL,
	PRIMARY KEY(`sleeve_id`, `expiry`, `strike`, `kind`),
	FOREIGN KEY (`sleeve_id`) REFERENCES `rt_sleeve`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `rt_path` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`weight` real DEFAULT 0 NOT NULL,
	`created_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`updated_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL
);
--> statement-breakpoint
CREATE TABLE `rt_path_point` (
	`path_id` text NOT NULL,
	`date` text NOT NULL,
	`price` real NOT NULL,
	`action` text NOT NULL,
	`sell_pct` integer,
	PRIMARY KEY(`path_id`, `date`),
	FOREIGN KEY (`path_id`) REFERENCES `rt_path`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `rt_sleeve` (
	`id` text PRIMARY KEY NOT NULL,
	`build_id` text NOT NULL,
	`position` integer NOT NULL,
	`contracts` integer NOT NULL,
	FOREIGN KEY (`build_id`) REFERENCES `rt_build`(`id`) ON UPDATE no action ON DELETE cascade
);
