import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { OpenAI } from "npm:openai@^4.27.0";
import { RecursiveCharacterTextSplitter } from "npm:langchain/text_splitter";

// These environment variables are configured in the Supabase Dashboard
const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY");

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !OPENAI_API_KEY) {
  throw new Error("Missing environment variables.");
}

const openai = new OpenAI({ apiKey: OPENAI_API_KEY });
const supabaseAdmin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

const splitter = new RecursiveCharacterTextSplitter({
  chunkSize: 1000,
  chunkOverlap: 200,
});

serve(async (req) => {
  try {
    const { documents } = await req.json();

    if (!documents || !Array.isArray(documents)) {
      return new Response(
        JSON.stringify({ error: "Missing 'documents' in request body" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }
    
    // Clear the table before inserting new data
    const { error: deleteError } = await supabaseAdmin
      .from("knowledge_base")
      .delete()
      .gt("id", "00000000-0000-0000-0000-000000000000");

    if (deleteError) {
      console.error("Error deleting old documents:", deleteError);
      throw deleteError;
    }

    for (const doc of documents) {
      const chunks = await splitter.splitText(doc.content);

      for (const chunk of chunks) {
        const embeddingResponse = await openai.embeddings.create({
          model: "text-embedding-3-small",
          input: chunk,
        });

        const [{ embedding }] = embeddingResponse.data;

        const { error } = await supabaseAdmin.from("knowledge_base").insert({
          content: chunk,
          metadata: doc.metadata,
          embedding: embedding,
        });

        if (error) {
          console.error("Error inserting chunk:", error);
          throw error;
        }
      }
    }

    return new Response(JSON.stringify({ success: true, message: `${documents.length} documents processed.` }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error(error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});