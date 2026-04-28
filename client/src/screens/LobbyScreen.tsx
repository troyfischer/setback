import { StyleSheet, Text, TextInput, View } from "react-native";

import { ActionButton } from "../components/ActionButton";
import type { CurrentUser, GameRecord, TeamRecord } from "../types/setback";

type Props = {
    accessToken: string;
    activeGameId: number | null;
    busyAction: string | null;
    createdGame: GameRecord | null;
    currentUser: CurrentUser | null;
    error: string | null;
    gameIdInput: string;
    joinCode: string;
    knownTeams: TeamRecord[];
    notice: string | null;
    onChangeGameId: (value: string) => void;
    onChangeJoinCode: (value: string) => void;
    onChangeTeamId: (value: string) => void;
    onCreateGame: () => void;
    onCreateTeam: () => void;
    onJoinGame: () => void;
    onJoinTeam: () => void;
    onLeaveTable: () => void;
    onLogout: () => void;
    onStartGame: () => void;
    teamIdInput: string;
};

export function LobbyScreen({
    accessToken,
    activeGameId,
    busyAction,
    createdGame,
    currentUser,
    error,
    gameIdInput,
    joinCode,
    knownTeams,
    notice,
    onChangeGameId,
    onChangeJoinCode,
    onChangeTeamId,
    onCreateGame,
    onCreateTeam,
    onJoinGame,
    onJoinTeam,
    onLeaveTable,
    onLogout,
    onStartGame,
    teamIdInput,
}: Props) {
    const inTable = Boolean(activeGameId);
    const shareCode =
        createdGame?.join_code && createdGame.id === activeGameId
            ? createdGame.join_code
            : null;
    const displayName =
        currentUser?.given_name ||
        currentUser?.name ||
        currentUser?.sub ||
        "player";

    return (
        <View style={styles.wrapper}>
            <View style={styles.header}>
                <View>
                    <Text style={styles.brand}>Setback</Text>
                    <Text style={styles.greeting}>Welcome, {displayName}.</Text>
                </View>
                <ActionButton
                    busy={busyAction === "Logout"}
                    disabled={!accessToken}
                    label="Sign Out"
                    onPress={onLogout}
                    tone="ghost"
                />
            </View>

            {error ? (
                <View style={[styles.banner, styles.errorBanner]}>
                    <Text style={styles.bannerText}>{error}</Text>
                </View>
            ) : null}
            {notice && !error ? (
                <View style={[styles.banner, styles.noticeBanner]}>
                    <Text style={styles.bannerText}>{notice}</Text>
                </View>
            ) : null}

            {!inTable ? (
                <>
                    <View style={styles.card}>
                        <Text style={styles.cardEyebrow}>Host</Text>
                        <Text style={styles.cardTitle}>Start a new table</Text>
                        <Text style={styles.cardBody}>
                            Create a table and share the join code so the other
                            three seats can fill.
                        </Text>
                        <ActionButton
                            busy={busyAction === "Create game"}
                            label="Create Game"
                            onPress={onCreateGame}
                        />
                    </View>

                    <View style={styles.divider}>
                        <View style={styles.dividerLine} />
                        <Text style={styles.dividerText}>or</Text>
                        <View style={styles.dividerLine} />
                    </View>

                    <View style={styles.card}>
                        <Text style={styles.cardEyebrow}>Guest</Text>
                        <Text style={styles.cardTitle}>Join a table</Text>
                        <Text style={styles.cardBody}>
                            Enter the join code your host shared.
                        </Text>

                        <View style={styles.formRow}>
                            <View style={styles.flexField}>
                                <Text style={styles.label}>Game number</Text>
                                <TextInput
                                    keyboardType="numeric"
                                    onChangeText={onChangeGameId}
                                    placeholder="42"
                                    placeholderTextColor="#8ca3bf"
                                    style={styles.input}
                                    value={gameIdInput}
                                />
                            </View>
                            <View style={styles.flexField}>
                                <Text style={styles.label}>Join code</Text>
                                <TextInput
                                    autoCapitalize="none"
                                    autoCorrect={false}
                                    onChangeText={onChangeJoinCode}
                                    placeholder="table secret"
                                    placeholderTextColor="#8ca3bf"
                                    style={styles.input}
                                    value={joinCode}
                                />
                            </View>
                        </View>
                        <ActionButton
                            busy={busyAction === "Join game"}
                            label="Join Game"
                            onPress={onJoinGame}
                            tone="secondary"
                        />
                    </View>
                </>
            ) : (
                <View style={styles.card}>
                    <Text style={styles.cardEyebrow}>Table</Text>
                    <Text style={styles.cardTitle}>Game #{activeGameId}</Text>
                    <Text style={styles.cardBody}>
                        Set up teams, then start the game when everyone is
                        seated.
                    </Text>

                    {shareCode ? (
                        <View style={styles.codeBox}>
                            <Text style={styles.codeLabel}>
                                Share this join code
                            </Text>
                            <Text style={styles.codeValue}>{shareCode}</Text>
                        </View>
                    ) : null}

                    <View style={styles.teamSection}>
                        <Text style={styles.sectionTitle}>Teams</Text>
                        <Text style={styles.sectionBody}>
                            Create a team, then have your partner join it with
                            the same number.
                        </Text>

                        <View style={styles.formRow}>
                            <View style={styles.flexField}>
                                <Text style={styles.label}>Team number</Text>
                                <TextInput
                                    keyboardType="numeric"
                                    onChangeText={onChangeTeamId}
                                    placeholder="1"
                                    placeholderTextColor="#8ca3bf"
                                    style={styles.input}
                                    value={teamIdInput}
                                />
                            </View>
                            <View style={styles.teamButtons}>
                                <ActionButton
                                    busy={busyAction === "Create team"}
                                    label="Create Team"
                                    onPress={onCreateTeam}
                                    tone="secondary"
                                />
                                <ActionButton
                                    busy={busyAction === "Join team"}
                                    label="Join Team"
                                    onPress={onJoinTeam}
                                    tone="ghost"
                                />
                            </View>
                        </View>

                        {knownTeams.length > 0 ? (
                            <View style={styles.teamList}>
                                {knownTeams.map((team) => (
                                    <View
                                        key={team.id}
                                        style={styles.teamBadge}
                                    >
                                        <Text style={styles.teamBadgeText}>
                                            Team {team.id}
                                        </Text>
                                    </View>
                                ))}
                            </View>
                        ) : null}
                    </View>

                    <View style={styles.actionRow}>
                        <ActionButton
                            busy={busyAction === "Start game"}
                            label="Start Game"
                            onPress={onStartGame}
                        />
                        <ActionButton
                            label="Leave Table"
                            onPress={onLeaveTable}
                            tone="ghost"
                        />
                    </View>
                </View>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    actionRow: {
        columnGap: 10,
        flexDirection: "row",
        flexWrap: "wrap",
        rowGap: 10,
    },
    banner: {
        borderRadius: 14,
        paddingHorizontal: 16,
        paddingVertical: 12,
    },
    bannerText: {
        color: "#fdfefe",
        fontSize: 14,
        fontWeight: "600",
    },
    brand: {
        color: "#f8fbff",
        fontSize: 26,
        fontWeight: "900",
        letterSpacing: 0.5,
    },
    card: {
        backgroundColor: "#fffaf2",
        borderRadius: 28,
        padding: 22,
        rowGap: 12,
        shadowColor: "#081120",
        shadowOffset: { height: 10, width: 0 },
        shadowOpacity: 0.18,
        shadowRadius: 24,
    },
    cardBody: {
        color: "#4e647f",
        fontSize: 14,
        lineHeight: 20,
    },
    cardEyebrow: {
        color: "#b54434",
        fontSize: 11,
        fontWeight: "800",
        letterSpacing: 1.6,
        textTransform: "uppercase",
    },
    cardTitle: {
        color: "#102947",
        fontSize: 22,
        fontWeight: "800",
    },
    codeBox: {
        backgroundColor: "#102947",
        borderRadius: 18,
        padding: 18,
        rowGap: 4,
    },
    codeLabel: {
        color: "#f7d774",
        fontSize: 11,
        fontWeight: "700",
        letterSpacing: 1.4,
        textTransform: "uppercase",
    },
    codeValue: {
        color: "#f8fbff",
        fontFamily: "Menlo",
        fontSize: 22,
        fontWeight: "800",
    },
    divider: {
        alignItems: "center",
        columnGap: 12,
        flexDirection: "row",
    },
    dividerLine: {
        backgroundColor: "rgba(247, 215, 116, 0.28)",
        flexGrow: 1,
        height: 1,
    },
    dividerText: {
        color: "#d2deee",
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 1.2,
        textTransform: "uppercase",
    },
    errorBanner: {
        backgroundColor: "rgba(150, 45, 36, 0.94)",
    },
    flexField: {
        flexGrow: 1,
        flexShrink: 1,
        minWidth: 180,
    },
    formRow: {
        columnGap: 12,
        flexDirection: "row",
        flexWrap: "wrap",
        rowGap: 12,
    },
    greeting: {
        color: "#d2deee",
        fontSize: 14,
        marginTop: 2,
    },
    header: {
        alignItems: "center",
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 12,
        justifyContent: "space-between",
    },
    input: {
        backgroundColor: "#edf3fa",
        borderColor: "#bfd1e7",
        borderRadius: 14,
        borderWidth: 1,
        color: "#0d1d31",
        fontSize: 16,
        paddingHorizontal: 14,
        paddingVertical: 12,
    },
    label: {
        color: "#0d1d31",
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.4,
        marginBottom: 6,
        textTransform: "uppercase",
    },
    noticeBanner: {
        backgroundColor: "rgba(31, 134, 99, 0.92)",
    },
    sectionBody: {
        color: "#4e647f",
        fontSize: 13,
        lineHeight: 18,
    },
    sectionTitle: {
        color: "#102947",
        fontSize: 16,
        fontWeight: "800",
    },
    teamBadge: {
        backgroundColor: "#f1d7a1",
        borderRadius: 999,
        paddingHorizontal: 14,
        paddingVertical: 8,
    },
    teamBadgeText: {
        color: "#5b2f16",
        fontSize: 13,
        fontWeight: "700",
    },
    teamButtons: {
        alignItems: "flex-start",
        columnGap: 10,
        flexDirection: "row",
        flexWrap: "wrap",
        paddingTop: 24,
        rowGap: 8,
    },
    teamList: {
        columnGap: 10,
        flexDirection: "row",
        flexWrap: "wrap",
        rowGap: 10,
    },
    teamSection: {
        backgroundColor: "#eff4fa",
        borderRadius: 18,
        padding: 16,
        rowGap: 10,
    },
    wrapper: {
        alignSelf: "center",
        maxWidth: 640,
        rowGap: 16,
        width: "100%",
    },
});
