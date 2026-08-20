package discord

import (
	"fmt"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/Karitham/corde"
	"github.com/rs/zerolog/log"
)

type Profile struct {
	User
	CharacterCount int
	Favorite       Character
	Balance        int // Added to match your Telegram Economy DB (coins)
}

func (b *Bot) profile(m *corde.Mux) {
	m.SlashCommand("view", trace(b.profileView))
	m.Route("edit", func(m *corde.Mux) {
		m.SlashCommand("quote", trace(b.profileEditQuote))
		m.Route("favorite", func(m *corde.Mux) {
			m.SlashCommand("", trace(b.profileEditFavorite))
			m.Autocomplete("id", trace(b.profileEditFavoriteComplete))
		})
		m.SlashCommand("anilist", trace(b.profileEditAnilistURL))
	})
}

func (b *Bot) profileView(w corde.ResponseWriter, i *corde.Request[corde.SlashCommandInteractionData]) {
	user := i.Member.User
	if len(i.Data.Resolved.Users) > 0 {
		user = i.Data.Resolved.Users.First()
	}

	data, err := b.Store.Profile(i.Context, user.ID)
	if err != nil {
		log.Ctx(i.Context).Err(err).Msg("Error getting user's profile")
		w.Respond(corde.NewResp().Content("❌ An error occurred dialing the database, please try again later.").Ephemeral())
		return
	}

	anilistURLDesc := ""
	if data.AnilistURL != "" {
		anilistURLDesc = fmt.Sprintf("Find them on [Anilist](%s)", data.AnilistURL)
	}

	// Make the discord embed look clean and matched with your telegram bot vibes
	resp := corde.NewEmbed().
		Title(user.Username + "'s Profile").
		URL(fmt.Sprintf("https://waifugui.karitham.dev/#/list/%s", user.ID.String())).
		Descriptionf(
			"\"*%s*\"\n\n**%s** last rolled %s ago.\n**Tokens:** %d\n**Characters:** %d\n**Favorite:** %s\n\n%s",
			data.Quote,
			user.Username,
			time.Since(data.Date.UTC()).Truncate(time.Second),
			data.Tokens, // Agar Balance/Coins bhi dikhana hai toh yahan data.Balance pass kar dena
			data.CharacterCount,
			data.Favorite.Name,
			anilistURLDesc,
		).Color(0x2b2d31) // Nice clean dark grey color

	if data.Favorite.Image != "" {
		resp.Thumbnail(corde.Image{URL: data.Favorite.Image})
	}

	w.Respond(resp)
}

func (b *Bot) profileEditFavorite(w corde.ResponseWriter, i *corde.Request[corde.SlashCommandInteractionData]) {
	optID, _ := i.Data.Options.Int64("id")
	err := b.Store.SetUserFavorite(i.Context, i.Member.User.ID, optID)
	if err != nil {
		log.Ctx(i.Context).Err(err).Stringer("user", i.Member.User.ID).Int64("character", optID).Msg("Error setting user's favorite character")
		w.Respond(corde.NewResp().Content("❌ An error occurred setting this character").Ephemeral())
		return
	}

	w.Respond(corde.NewResp().Contentf("✅ Favorite character successfully set as char ID %d", optID).Ephemeral())
}

func (b *Bot) profileEditFavoriteComplete(w corde.ResponseWriter, i *corde.Request[corde.AutocompleteInteractionData]) {
	id, err := i.Data.Options.String("id")
	if err != nil {
		idInt, _ := i.Data.Options.Int("id")
		id = strconv.Itoa(idInt)
	}

	chars, err := b.Store.CharsStartingWith(i.Context, i.Member.User.ID, id)
	if err != nil {
		log.Err(err).Stringer("user", i.Member.User.ID).Msg("Error getting user's characters")
		return
	}

	// 🔥 FIX: Changed chars[25:] to chars[:25]. 
	// This ensures we ONLY send the FIRST 25 items, avoiding a Discord API Crash.
	if len(chars) > 25 {
		chars = chars[:25]
	}

	resp := corde.NewResp()
	for _, c := range chars {
		resp.Choice(c.Name, c.ID)
	}

	w.Autocomplete(resp)
}

func (b *Bot) profileEditAnilistURL(w corde.ResponseWriter, i *corde.Request[corde.SlashCommandInteractionData]) {
	anilistURL, _ := i.Data.Options.String("url")
	parsedURL, err := url.Parse(anilistURL)
	if err != nil {
		w.Respond(corde.NewResp().Content("❌ Invalid URL").Ephemeral())
		return
	}

	if parsedURL.Host != "anilist.co" {
		w.Respond(corde.NewResp().Content("❌ Invalid Anilist URL. Make sure it's anilist.co").Ephemeral())
		return
	}

	if !strings.HasPrefix(parsedURL.Path, "/user/") {
		w.Respond(corde.NewResp().Content("❌ Invalid Anilist URL format. Example: https://anilist.co/user/{YourName}").Ephemeral())
		return
	}

	err = b.Store.SetUserAnilistURL(i.Context, i.Member.User.ID, anilistURL)
	if err != nil {
		log.Ctx(i.Context).Err(err).Stringer("user", i.Member.User.ID).Msg("Error setting user's anilist url")
		w.Respond(corde.NewResp().Content("❌ An error occurred setting your anilist url").Ephemeral())
		return
	}

	w.Respond(corde.NewResp().Contentf("✅ Anilist URL successfully set to %s", anilistURL).Ephemeral())
}

func (b *Bot) profileEditQuote(w corde.ResponseWriter, i *corde.Request[corde.SlashCommandInteractionData]) {
	quote, _ := i.Data.Options.String("value")
	if len(quote) > 1024 {
		w.Respond(corde.NewResp().Content("❌ Quote is too long (Max limit is 1024 characters)").Ephemeral())
		return
	}

	err := b.Store.SetUserQuote(i.Context, i.Member.User.ID, quote)
	if err != nil {
		log.Ctx(i.Context).Err(err).Stringer("user", i.Member.User.ID).Str("quote", quote).Msg("Error setting user's quote")
		w.Respond(corde.NewResp().Content("❌ An error occurred setting your quote").Ephemeral())
		return
	}

	w.Respond(corde.NewResp().Content("✅ Quote successfully set").Ephemeral())
}
